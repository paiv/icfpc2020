
TEST_TARGET ?= debug

.PHONY: all release debug test clean

all: release

release: CMAKE_ARGS=-DCMAKE_BUILD_TYPE=Release
release: TARGET_DIR=build/release

debug: CMAKE_ARGS=-DCMAKE_BUILD_TYPE=Debug
debug: TARGET_DIR=build/debug

test: CFLAGS=-DGALAXY_TEST
test: $(TEST_TARGET)

release debug test: galaxy

galaxy: $(TARGET_DIR)/galaxy
.PHONY: galaxy

$(TARGET_DIR)/galaxy: $(wildcard *.cpp) $(wildcard *.h) $(TARGET_DIR)/Makefile
	cd $(TARGET_DIR) && $(MAKE)

$(TARGET_DIR)/Makefile:
	mkdir -p $(TARGET_DIR) \
		&& cd $(TARGET_DIR) \
		&& CFLAGS=$(CFLAGS) cmake $(CMAKE_ARGS) ../..


clean:
	[ -d build ] && rm -r build
