cmake_minimum_required(VERSION 3.21)
project(gumbo_frontend LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

FetchContent_Declare(
  raylib
  GIT_REPOSITORY https://github.com/raysan5/raylib.git
  GIT_TAG 5.5
)
FetchContent_MakeAvailable(raylib)

FetchContent_Declare(
  ixwebsocket
  GIT_REPOSITORY https://github.com/machinezone/IXWebSocket.git
  GIT_TAG v11.4.5
)
# IXWebSocket enables zlib by default, but many clean Windows setups do not
# provide a preinstalled zlib package discoverable by CMake.
#
# Disable optional compression support so first-time frontend builds work
# without requiring users to install external zlib development artifacts.
set(USE_ZLIB OFF CACHE BOOL "Disable zlib for vendored IXWebSocket" FORCE)
FetchContent_MakeAvailable(ixwebsocket)

FetchContent_Declare(
  json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG v3.11.3
)
FetchContent_MakeAvailable(json)

add_executable(gumbo_frontend
  src/main.cpp
  src/App.cpp
  src/App.hpp
  src/BackendProcess.cpp
  src/BackendProcess.hpp
  src/WebSocketClient.cpp
  src/WebSocketClient.hpp
  src/Layout.cpp
  src/Layout.hpp
)

target_link_libraries(gumbo_frontend PRIVATE raylib ixwebsocket nlohmann_json::nlohmann_json)

if(WIN32)
  target_link_libraries(gumbo_frontend PRIVATE winhttp ws2_32 crypt32)
endif()
