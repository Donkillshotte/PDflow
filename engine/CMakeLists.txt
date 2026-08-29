cmake_minimum_required(VERSION 3.16)
project(dpn LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(Eigen3 3.3 REQUIRED NO_MODULE)

add_library(dpn SHARED
  src/csr.cpp
  src/solvers.cpp
  src/c_api.cpp
)
target_include_directories(dpn
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_link_libraries(dpn PUBLIC Eigen3::Eigen)
target_compile_options(dpn PRIVATE -O3 -fno-math-errno)

add_executable(dpn_test tests/test_native.cpp)
target_link_libraries(dpn_test PRIVATE dpn)
target_include_directories(dpn_test PRIVATE include)

install(TARGETS dpn LIBRARY DESTINATION lib)
install(DIRECTORY include/dpn DESTINATION include)
