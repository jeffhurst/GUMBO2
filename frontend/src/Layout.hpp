#pragma once

#include "raylib.h"

struct LayoutRects {
    Rectangle conversation;
    Rectangle input;
    Rectangle fdg;
    Rectangle console;
};

LayoutRects ComputeLayout(int screenWidth, int screenHeight);
