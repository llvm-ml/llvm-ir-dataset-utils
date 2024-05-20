cmake_minimum_required(VERSION 3.20)

project(RemoveFunctionBodyPass)

set(LT_LLVM_INSTALL_DIR "" CACHE PATH "LLVM installation directory")
list(APPEND CMAKE_PREFIX_PATH "${LT_LLVM_INSTALL_DIR}/lib/cmake/llvm/")

set (CMAKE_CXX_STANDARD 17 CACHE STRING "")

find_package(LLVM REQUIRED CONFIG)

include_directories(SYSTEM ${LLVM_INCLUDE_DIRS})

if(NOT LLVM_ENABLE_RTTI)
  set(CMKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fno-rtti")
endif()

message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "Using LLVMConfig.cmake in: ${LLVM_DIR}")

add_library(RemoveFunctionBody SHARED RemoveFunctionBody.cpp)
target_link_libraries(RemoveFunctionBody "$<$<PLATFORM_ID:Darwin>:-undefined dynamic_lookup>")

# separate_arguments(LLVM_DEFINITIONS_LIST NATIVE_COMMAND ${LLVM_DEFINITIONS})
# add_definitions(${LLVM_DEFINITIONS_LIST})
# include_directories(${LLVM_INCLUDE_DIRS})
#
# include_directories(${CMAKE_SOURCE_DIR}/include)
#
# # Link with passes library
# llvm_map_components_to_libnames(llvm_libs passes)
# add_subdirectory(RemoveFunctionBodyPass)
#
# # add_llvm_pass_plugin(RemoveFunctionBody ./src/RemoveFunctionBody.cpp)


