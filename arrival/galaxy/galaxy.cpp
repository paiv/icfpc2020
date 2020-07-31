#include <cinttypes>
#include <map>
#include <memory>
#include <set>

#include "galaxy_machine.inc"


typedef uint8_t u8;
typedef int32_t i32;
typedef uint32_t u32;
typedef int64_t i64;
typedef uint64_t u64;


extern "C" {
    const void load_machine(const i64* image);
    const i64* evaluate(u32 size, const i64* request);
}


[[noreturn, gnu::nodebug]] static inline void __attribute__((__always_inline__, __nodebug__))
fatal_error() {
    abort();
}

typedef struct expr {
    atom_kind kind;
    expr* l;
    expr* r;
    i64 number;
    expr* evaluated;
} expr;


typedef struct node {
    node* parent;
    expr* e;
} node;


static node*
make_node(expr* e = nullptr, node* parent = nullptr) {
    node* n = (node*) calloc(1, sizeof(node));
    n->parent = parent;
    n->e = e;
    return n;
}


static void
free_node(node* n) {
    while (n != nullptr) {
        node* p = n->parent;
        free(n);
        n = p;
    }
}


static node*
stack_push(node* stack, expr* e) {
    return make_node(e, stack);
}


static node*
stack_pop(node* stack) {
    node* tail = stack->parent;
    stack->parent = nullptr;
    free_node(stack);
    return tail;
}


typedef struct mem_arena {
    mem_arena* parent;
    u32 used;
    u8 buf[200000];
} mem_arena;


static mem_arena* rom;
static mem_arena* memory;


static void*
mem_alloc(u32 count, u32 size) {
    u64 total = u64(count) * size;
    if (total > sizeof(mem_arena::buf)) {
        fatal_error();
    }

    if (memory == nullptr || memory->used + total > sizeof(mem_arena::buf)) {
        auto* block = (mem_arena*) calloc(1, sizeof(mem_arena));
        block->parent = memory;
        memory = block;
    }

    u8* p = &memory->buf[memory->used];
    memory->used += total;
    return p;
}


static void
mem_release(mem_arena* block) {
    while (block != nullptr) {
        auto* p = block->parent;
        free(block);
        block = p;
    }
}


static expr*
make_atom(atom_kind kind);


static expr*
make_atom(atom_kind kind) {
    expr* e = (expr*)mem_alloc(1, sizeof(expr));
    e->kind = kind;
    return e;
}


static expr*
make_ap(expr* l, expr* r) {
    expr* e = (expr*)mem_alloc(1, sizeof(expr));
    e->kind = atom_kind::ap;
    e->l = l;
    e->r = r;
    return e;
}


static expr*
make_nil() {
    return make_atom(atom_kind::nil);
}


static expr*
make_t() {
    return make_atom(atom_kind::t);
}


static expr*
make_f() {
    return make_atom(atom_kind::f);
}


static expr*
make_cons() {
    return make_atom(atom_kind::cons);
}


static expr*
make_number(i64 value) {
    expr* e = make_atom(atom_kind::number);
    e->number = value;
    return e;
}


static node*
decoder_reduce(node* stack) {
    while (stack->parent->e != nullptr && stack->parent->parent->e == nullptr) {
        expr* r = stack->e;
        expr* l = stack->parent->e;
        node* tail = stack->parent->parent->parent;
        stack->parent->parent->parent = nullptr;
        free_node(stack);
        auto* cons = make_ap(make_ap(make_cons(), l), r);
        stack = stack_push(tail, cons);
    }
    return stack;
}


static u8
number_nibs(u64 number) {
    u8 bits = 16;
    u64 mask = 0xf000000000000000;
    if ((number & 0xffffffff00000000) == 0) {
        bits = 8;
        mask = 0xf0000000;
    }
    for (; (mask != 0) && (number & mask) == 0; mask >>= 4, --bits) {
    }
    return bits;
}


expr*
decode(const char* text) {
    node* stack = make_node();
    stack = stack_push(stack, nullptr);
    stack = stack_push(stack, nullptr);

    const char* p = text;
    u8 state = 0;
    u8 neg = 0;
    u8 bits = 0;
    i64 number = 0;

    while (1) {
        char c = *p++;
        if (c == '\0') {
            break;
        }
        switch (state) {

        case 0:
            if (c == '0') {
                state = 1;
            }
            else if (c == '1') {
                state = 2;
            }
            break;

        case 1:
            if (c == '0') {
                state = 0;
                stack = stack_push(stack, make_nil());
                stack = decoder_reduce(stack);
            }
            else if (c == '1') {
                state = 3;
                neg = 0;
                bits = 0;
            }
            break;

        case 2:
            if (c == '0') {
                state = 3;
                neg = 1;
                bits = 0;
            }
            else if (c == '1') {
                state = 0;
                stack = stack_push(stack, nullptr);
            }
            break;

        case 3:
            if (c == '0') {
                if (bits == 0) {
                    state = 0;
                    stack = stack_push(stack, make_number(0));
                    stack = decoder_reduce(stack);
                }
                else {
                    state = 4;
                    bits *= 4;
                    number = 0;
                }
            }
            else if (c == '1') {
                ++bits;
            }
            break;

        case 4:
            number = (number << 1) | (c != '0' ? 1 : 0);
            if (--bits == 0) {
                state = 0;
                stack = stack_push(stack, make_number(neg ? -number : number));
                stack = decoder_reduce(stack);
            }
            break;
        }
    }

    expr* e = stack->e;
    free_node(stack);
    return e;
}


static const char*
encode(expr* tree) {
    const u32 buf_size = 20000;
    static char buf[buf_size];
    const char* buf_end = &buf[buf_size-1];

    node* stack = make_node(tree);

    char* p = buf;
    expr* item = nullptr;
    u8 state = 0;
    i64 number;
    u8 nibs;
    u64 bits;

    for (u8 done = 0; done == 0; ) {
        if (p == buf_end) {
            fatal_error();
        }

        switch (state) {

        case 0:
            if (stack == nullptr) {
                done = 1;
                *p++ = '\0';
                break;
            }
            item = stack->e;
            stack = stack_pop(stack);
            if (item->r != nullptr) {
                stack = stack_push(stack, item->r);
            }
            if (item->l != nullptr) {
                stack = stack_push(stack, item->l);
            }
            switch (item->kind) {
            case atom_kind::ap:
                if (item->l != nullptr && item->l->kind == atom_kind::ap) {
                    if (item->l->l != nullptr && item->l->l->kind == atom_kind::cons) {
                        state = 1;
                        *p++ = '1';
                    }
                }
                break;
            case atom_kind::cons: break;
            case atom_kind::nil:
                state = 1;
                *p++ = '0';
                break;
            case atom_kind::number:
                state = 1;
                *p++ = (item->number < 0 ? '1' : '0');
                break;
            default: fatal_error();
            }
            break;

        case 1:
            state = 0;
            switch (item->kind) {
            case atom_kind::ap: *p++ = '1'; break;
            case atom_kind::nil: *p++ = '0'; break;
            case atom_kind::number:
                state = 3;
                *p++ = (item->number < 0 ? '0' : '1');
                nibs = number_nibs(item->number);
                bits = (u64(8) << ((nibs - 1) * 4));
                break;
            default: fatal_error();
            }
            break;

        case 3:
            *p++ = (nibs > 0) ? '1' : '0';
            if (nibs == 0) {
                number = (item->number < 0) ? -item->number : item->number;
                state = (number == 0) ? 0 : 4;
            }
            else {
                --nibs;
            }
            break;

        case 4:
            *p++ = (number & bits) == 0 ? '0' : '1';
            bits >>= 1;
            if (bits == 0) {
                state = 0;
            }
            break;
        }
    }

    return buf;
}


static
expr* machine = nullptr;

static
expr* function_table[2000];


static node*
machine_decode_reduce(node* stack) {
    while (stack->parent->e != nullptr && stack->parent->parent->e == nullptr) {
        expr* r = stack->e;
        stack = stack_pop(stack);
        expr* l = stack->e;
        stack = stack_pop(stack);
        stack = stack_pop(stack);
        expr* ap = make_ap(l, r);
        stack = stack_push(stack, ap);
    }
    return stack;
}


static expr*
machine_decode_expr(const i64* reader, u32 scan_size) {
    node* stack = nullptr;

    stack = make_node();
    stack = stack_push(stack, make_nil());
    stack = stack_push(stack, make_nil());

    while (scan_size > 0) {
        expr* token = make_atom(atom_kind(*reader++));

        switch (token->kind) {
        case atom_kind::ap:
            if (scan_size < 1) fatal_error();
            --scan_size;
            stack = stack_push(stack, nullptr);
            break;

        case atom_kind::cons:
        case atom_kind::nil:
        case atom_kind::neg:
        case atom_kind::c:
        case atom_kind::b:
        case atom_kind::s:
        case atom_kind::isnil:
        case atom_kind::car:
        case atom_kind::eq:
        case atom_kind::mul:
        case atom_kind::add:
        case atom_kind::lt:
        case atom_kind::div:
        case atom_kind::i:
        case atom_kind::t:
        case atom_kind::f:
        case atom_kind::cdr:
        case atom_kind::galaxy:
            if (scan_size < 1) fatal_error();
            --scan_size;
            stack = stack_push(stack, token);
            stack = machine_decode_reduce(stack);
            break;

        case atom_kind::number:
        case atom_kind::FUN:
            if (scan_size < 2) fatal_error();
            scan_size -= 2;
            token->number = *reader++;
            stack = stack_push(stack, token);
            stack = machine_decode_reduce(stack);
            break;

        case atom_kind::SCAN:
        case atom_kind::DEF:
        case atom_kind::GG:
            fatal_error();
        }
    }

    expr* e = stack->e;
    free_node(stack);
    return e;
}


static expr*
load_machine_image(const i64* reader) {
    *function_table = {};
    u8 state = 0;
    u32 scan_size = 0;
    expr* function = nullptr;
    expr* galaxy = nullptr;

    for (u8 done = 0; done == 0; ) {
        atom_kind token_kind = (atom_kind) *reader++;

        switch (state) {

        case 0:
            switch (token_kind) {
            case atom_kind::SCAN:
                state = 1;
                scan_size = *reader++;
                break;
            case atom_kind::GG: done = 1; break;
            default: fatal_error();
            }
            break;

        case 1:
            switch (token_kind) {
            case atom_kind::galaxy:
            case atom_kind::FUN:
                if (scan_size < 2) fatal_error();
                scan_size -= 2;
                state = 2;
                function = make_atom(token_kind);
                function->number = *reader++;
                if (token_kind == atom_kind::galaxy) {
                    galaxy = function;
                }
                break;
            default: fatal_error();
            }
            break;

        case 2:
            switch (token_kind) {
            case atom_kind::DEF:
                if (scan_size < 1) fatal_error();
                --scan_size;
                state = 0;
                function_table[function->number] = machine_decode_expr(reader, scan_size);
                reader += scan_size;
                break;
            default: fatal_error();
            }
            break;
        }
    }

    return galaxy;
}


template<class T, u32 N>
constexpr u32
ElementCount(T(&)[N]) {
    return N;
}


static i64*
write_machine_image(i64* p, expr* e) {
    node* fringe = nullptr;
    fringe = stack_push(fringe, e);
    while (fringe != nullptr) {
        expr* e = fringe->e;
        fringe = stack_pop(fringe);
        if (e->r != nullptr) {
            fringe = stack_push(fringe, e->r);
        }
        if (e->l != nullptr) {
            fringe = stack_push(fringe, e->l);
        }

        switch(e->kind) {
        case atom_kind::ap:
        case atom_kind::cons:
        case atom_kind::nil:
        case atom_kind::neg:
        case atom_kind::c:
        case atom_kind::b:
        case atom_kind::s:
        case atom_kind::isnil:
        case atom_kind::car:
        case atom_kind::eq:
        case atom_kind::mul:
        case atom_kind::add:
        case atom_kind::lt:
        case atom_kind::div:
        case atom_kind::i:
        case atom_kind::t:
        case atom_kind::f:
        case atom_kind::cdr:
            *p++ = u8(e->kind);
            break;

        case atom_kind::number:
        case atom_kind::FUN:
            *p++ = u8(e->kind);
            *p++ = e->number;
            break;

        case atom_kind::galaxy:
        case atom_kind::SCAN:
        case atom_kind::DEF:
        case atom_kind::GG:
            fatal_error();
        }

    }
    return p;
}


static i64*
machine_encode_result(expr* e, u32* size = nullptr) {
    static i64 dump[100000];
    i64* p = dump;
    p = write_machine_image(p, e);
    *p++ = u8(atom_kind::GG);
    if (p > dump + sizeof(dump)) {
        fatal_error();
    }
    if (size != nullptr) {
        *size = p - dump;
    }
    return dump;
}


static void
check_machine() {
    static i64 dump[ElementCount(galaxy_machine_image)];
    i64* p = dump;

    for (u32 i = 1; i < ElementCount(function_table); ++i) {
        expr* e = function_table[i];
        if (e == nullptr) {
            continue;
        }

        *p++ = u8(atom_kind::SCAN);
        auto* n = p++;
        *p++ = u8(atom_kind::FUN);
        *p++ = i;
        *p++ = u8(atom_kind::DEF);
        p = write_machine_image(p, e);
        *n = p - n - 1;
    }

    expr* galaxy = function_table[0];
    *p++ = u8(atom_kind::SCAN);
    auto* n = p++;
    *p++ = u8(atom_kind::galaxy);
    *p++ = 0;
    *p++ = u8(atom_kind::DEF);
    p = write_machine_image(p, galaxy);
    *n = p - n - 1;

    *p++ = u8(atom_kind::GG);

    if (p - dump != ElementCount(galaxy_machine_image)) {
        fatal_error();
    }

    for (u32 i = 0; i < ElementCount(galaxy_machine_image); ++i) {
        if (dump[i] != galaxy_machine_image[i]) {
            fatal_error();
        }
    }
}


static u8
equal(expr* a, expr* b) {
    node* walker1 = nullptr;
    node* walker2 = nullptr;
    walker1 = stack_push(walker1, a);
    walker2 = stack_push(walker2, b);

    while (walker1 != nullptr && walker2 != nullptr) {
        expr* a = walker1->e;
        expr* b = walker2->e;

        if (a->kind != b->kind) {
            break;
        }

        walker1 = stack_pop(walker1);
        walker2 = stack_pop(walker2);

        if (a->r != nullptr) {
            if (b->r == nullptr) {
                break;
            }
            walker1 = stack_push(walker1, a->r);
            walker2 = stack_push(walker2, b->r);
        }
        if (a->l != nullptr) {
            if (b->l == nullptr) {
                break;
            }
            walker1 = stack_push(walker1, a->l);
            walker2 = stack_push(walker2, b->l);
        }

        if (a->kind == atom_kind::number || a->kind == atom_kind::FUN) {
            if (a->number != b->number) {
                break;
            }
        }
    }

    if (walker1 == nullptr && walker2 == nullptr) {
        return 1;
    }

    free_node(walker1);
    free_node(walker2);
    return 0;
}


static expr*
galaxy_eval(expr* input);


static i64
as_number(expr* e) {
    expr* r = galaxy_eval(e);
    return r->number;
}


static expr*
galaxy_eval_ap1(expr* fun, expr* x) {
    switch (fun->kind) {
        case atom_kind::nil: return make_t();
        case atom_kind::neg: return make_number(-as_number(x));
        case atom_kind::i: return x;
        case atom_kind::isnil: return make_ap(x, make_ap(make_t(), make_ap(make_t(), make_f())));
        case atom_kind::car: return make_ap(x, make_t());
        case atom_kind::cdr: return make_ap(x, make_f());
        default: fatal_error();
    }
}


static expr*
galaxy_eval_ap2(expr* fun, expr* x, expr* y) {
    switch (fun->kind) {
    case atom_kind::t: return y;
    case atom_kind::f: return x;
    case atom_kind::add: return make_number(as_number(y) + as_number(x));
    case atom_kind::mul: return make_number(as_number(y) * as_number(x));
    case atom_kind::div: return make_number(as_number(y) / as_number(x));
    case atom_kind::lt: return (as_number(y) < as_number(x)) ? make_t() : make_f();
    case atom_kind::eq: return (as_number(y) == as_number(x)) ? make_t() : make_f();
    case atom_kind::cons: {
        auto* res = make_ap(make_ap(make_cons(), galaxy_eval(y)), galaxy_eval(x));
        res->evaluated = res;
        return res;
    }
    default: fatal_error();
    }
}


static expr*
galaxy_eval_ap3(expr* fun, expr* x, expr* y, expr* z) {
    switch (fun->kind) {
    case atom_kind::s: return make_ap(make_ap(z, x), make_ap(y, x));
    case atom_kind::c: return make_ap(make_ap(z, x), y);
    case atom_kind::b: return make_ap(z, make_ap(y, x));
    case atom_kind::cons: return make_ap(make_ap(x, z), y);
    default: fatal_error();
    }
}


static expr*
galaxy_eval_ap(expr* input) {
    auto* fun1 = galaxy_eval(input->l);
    expr* fun2 = nullptr;
    expr* fun3 = nullptr;
    expr* x = input->r;
    expr* y = nullptr;
    expr* z = nullptr;

    switch (fun1->kind) {
    case atom_kind::nil:
    case atom_kind::neg:
    case atom_kind::i:
    case atom_kind::isnil:
    case atom_kind::car:
    case atom_kind::cdr:
        return galaxy_eval_ap1(fun1, x);
    default: break;

    case atom_kind::ap:
        fun2 = galaxy_eval(fun1->l);
        y = fun1->r;

        switch (fun2->kind) {
        case atom_kind::t:
        case atom_kind::f:
        case atom_kind::add:
        case atom_kind::mul:
        case atom_kind::div:
        case atom_kind::lt:
        case atom_kind::eq:
        case atom_kind::cons:
            return galaxy_eval_ap2(fun2, x, y);
        default: break;

        case atom_kind::ap:
            fun3 = galaxy_eval(fun2->l);
            z = fun2->r;

            switch (fun3->kind) {
            case atom_kind::s:
            case atom_kind::c:
            case atom_kind::b:
            case atom_kind::cons:
                return galaxy_eval_ap3(fun3, x, y, z);

            default: break;
            }
            break;
        }
        break;
    }

    return input;
}


static expr*
galaxy_try_eval(expr* input) {
    if (input->evaluated != nullptr) {
        return input->evaluated;
    }

    switch (input->kind) {
    case atom_kind::ap:
        return galaxy_eval_ap(input);

    case atom_kind::cons:
    case atom_kind::nil:
    case atom_kind::neg:
    case atom_kind::c:
    case atom_kind::b:
    case atom_kind::s:
    case atom_kind::isnil:
    case atom_kind::car:
    case atom_kind::eq:
    case atom_kind::mul:
    case atom_kind::add:
    case atom_kind::lt:
    case atom_kind::div:
    case atom_kind::i:
    case atom_kind::t:
    case atom_kind::f:
    case atom_kind::cdr:
    case atom_kind::number:
        return input;

    case atom_kind::FUN:
    case atom_kind::galaxy:
        return function_table[input->number];

    case atom_kind::DEF:
    case atom_kind::SCAN:
    case atom_kind::GG:
        fatal_error();
    }
}


static expr*
galaxy_eval(expr* input) {
    for (expr* e = input; ;) {
        expr* r = galaxy_try_eval(e);
        if (r == e) {
        // if ((r == e) || (r->kind == atom_kind::ap && equal(r, e))) {
            input->evaluated = r;
            return r;
        }
        e = r;
    }
}


static void
load_galaxy_machine() {
    load_machine(galaxy_machine_image);
    // check_machine();
}


const void
load_machine(const i64* image) {
    mem_release(rom);
    machine = nullptr;
    rom = nullptr;

    if (image == nullptr) {
        return;
    }

    auto* save_memory = memory;
    memory = nullptr;

    machine = load_machine_image(image);

    rom = memory;
    memory = save_memory;
}


const i64*
evaluate(u32 request_size, const i64* request) {
    if (request == nullptr) {
        return nullptr;
    }

    if (machine == nullptr) {
        load_galaxy_machine();
    }

    expr* state = machine_decode_expr(request, request_size);

    expr* new_state = galaxy_eval(state);
    auto* res = machine_encode_result(new_state);

    mem_release(memory);
    memory = nullptr;

    return res;
}


#ifdef GALAXY_RENDERER

template <class I>
static void
print_array(const I* ar, u32 size) {
    printf("[");
    for (u32 i = 0; i + 1 < size; ++i) {
        printf("%lld, ", (i64) ar[i]);
    }
    printf("%lld", (i64) ar[size-1]);
    printf("]\n");
}


static void
print_encoded_array(expr* e) {
    u32 size = 0;
    i64* ar = machine_encode_result(e, &size);
    print_array(ar, size);
}


int main(int argc, char const *argv[]) {
    const i32 inputs[][2] = {
        {0, 0},
        {0, 0},
        {0, 0},
        {0, 0},
        {0, 0},
        {0, 0},
        {0, 0},
        {0, 0},
        {8, 4},
        {2, -8},
        {3, 6},
        {0, -14},
        {-4, 10},
        {9, -3},
        {-4, 10},
        {1, 4},
    };

    u32 scan_size = 0;
    i64* side = machine_encode_result(make_nil(), &scan_size);

    for (auto& mouse : inputs) {
        printf("\n");
        print_array(mouse, 2);

        load_machine(nullptr);
        load_galaxy_machine();

        expr* state = machine_decode_expr(side, scan_size-1);
        expr* event = make_ap(make_ap(make_cons(), make_number(mouse[0])), make_number(mouse[1]));
        expr* call = make_ap(make_ap(make_atom(atom_kind::galaxy), state), event);

        expr* result = galaxy_eval(call);

        i64 flag = as_number(result->l->r);
        expr* new_state = result->r->l->r;
        expr* frames = result->r->r->l->r;

#if 0
        printf("flag: %lld\n", flag);
        printf("state:\n");
        print_encoded_array(new_state);
        printf("frames:\n");
        print_encoded_array(frames);
#endif
        side = machine_encode_result(new_state, &scan_size);

        mem_release(memory);
        memory = nullptr;
    }

    return 0;
}
#endif
