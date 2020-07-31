cmake_minimum_required(VERSION 3.12)

set(CMAKE_CXX_STANDARD 17)

project(galaxy)

add_library(galaxy SHARED galaxy.cpp)

add_executable(render galaxy.cpp)
target_compile_definitions(render PRIVATE GALAXY_RENDERER=1)
