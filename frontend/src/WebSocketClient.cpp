#include "WebSocketClient.hpp"

#include <nlohmann/json.hpp>

WebSocketClient::~WebSocketClient() { close(); }

bool WebSocketClient::connect(const std::string& url) {
    socket_.setUrl(url);
    socket_.setOnMessageCallback([this](const ix::WebSocketMessagePtr& msg) {
        if (msg->type == ix::WebSocketMessageType::Open) {
            connected_ = true;
            return;
        }

        if (msg->type == ix::WebSocketMessageType::Message) {
            IncomingEvent event;
            try {
                auto parsed = nlohmann::json::parse(msg->str);
                event.type = parsed.value("type", "");
                event.message = parsed.value("message", "");
                event.text = parsed.value("text", "");
                event.level = parsed.value("level", "info");
                event.path = parsed.value("path", "");
            } catch (...) {
                event.type = "alert";
                event.level = "error";
                event.message = "Invalid JSON from backend";
            }
            std::scoped_lock lock(mutex_);
            events_.push(event);
            return;
        }

        if (msg->type == ix::WebSocketMessageType::Error) {
            std::scoped_lock lock(mutex_);
            IncomingEvent event;
            event.type = "alert";
            event.level = "error";
            event.message = msg->errorInfo.reason;
            events_.push(event);
        }
    });
    socket_.start();
    return true;
}

void WebSocketClient::sendUserMessage(const std::string& text) {
    nlohmann::json payload = {
        {"type", "user_message"},
        {"text", text},
    };
    socket_.send(payload.dump());
}

std::optional<IncomingEvent> WebSocketClient::pollEvent() {
    std::scoped_lock lock(mutex_);
    if (events_.empty()) {
        return std::nullopt;
    }
    auto event = events_.front();
    events_.pop();
    return event;
}

void WebSocketClient::close() {
    socket_.stop();
    connected_ = false;
}
