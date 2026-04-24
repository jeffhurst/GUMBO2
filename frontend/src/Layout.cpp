#include "Layout.hpp"

LayoutRects ComputeLayout(int screenWidth, int screenHeight) {
    const float leftWidth = static_cast<float>(screenWidth) * 0.45f;
    const float rightWidth = static_cast<float>(screenWidth) - leftWidth;
    const float inputHeight = 80.0f;
    const float consoleHeight = static_cast<float>(screenHeight) * 0.25f;

    LayoutRects rects{};
    rects.conversation = {0, 0, leftWidth, static_cast<float>(screenHeight) - inputHeight};
    rects.input = {0, static_cast<float>(screenHeight) - inputHeight, leftWidth, inputHeight};
    rects.fdg = {leftWidth, 0, rightWidth, static_cast<float>(screenHeight) - consoleHeight};
    rects.console = {leftWidth, static_cast<float>(screenHeight) - consoleHeight, rightWidth, consoleHeight};
    return rects;
}
