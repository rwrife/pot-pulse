#include "pp/config.h"

#include <cstdlib>

namespace pp {

std::string ConfigStore::hex_lower(const uint8_t* data, size_t n) {
    static const char* kHex = "0123456789abcdef";
    std::string out;
    out.reserve(n * 2);
    for (size_t i = 0; i < n; i++) {
        out.push_back(kHex[data[i] >> 4]);
        out.push_back(kHex[data[i] & 0xF]);
    }
    return out;
}

bool zone_index_of(const std::string& id, int* out) {
    if (id.size() == 2 && id[0] == 'z' && id[1] >= '1' && id[1] <= '9') {
        const int idx = id[1] - '1';
        if (idx < kZoneCount) {
            *out = idx;
            return true;
        }
    }
    return false;
}

void ConfigStore::load() {
    uint32_t ms = strtoul(
        kv_->get("interval_ms", std::to_string(settings_.sample_interval_ms))
            .c_str(),
        nullptr, 10);
    if (ms >= kMinSampleIntervalMs && ms <= kMaxSampleIntervalMs) {
        settings_.sample_interval_ms = ms;
    }
    for (int z = 0; z < kZoneCount; z++) {
        std::string n = kv_->get("zone_name_" + std::to_string(z), "");
        if (!n.empty() && n.size() <= size_t(kMaxZoneNameLen)) {
            settings_.zone_names[z] = n;
        }
    }
    tokens_.clear();
    std::string raw = kv_->get("pair_tokens", "");
    size_t pos = 0;
    while ((pos = raw.find(';')) != std::string::npos) {
        std::string rec = raw.substr(0, pos);
        raw.erase(0, pos + 1);
        size_t bar = rec.find('|');
        if (bar != std::string::npos && rec.size() - bar - 1 == 32) {
            PairingToken t;
            t.token = rec.substr(bar + 1);
            t.label = rec.substr(0, bar);
            tokens_.push_back(t);
        }
    }
    if (raw.size() == 32) {
        PairingToken t;
        t.token = raw;
        tokens_.push_back(t);
    }
}

void ConfigStore::save_settings() {
    kv_->put("interval_ms", std::to_string(settings_.sample_interval_ms));
    for (int z = 0; z < kZoneCount; z++) {
        kv_->put("zone_name_" + std::to_string(z), settings_.zone_names[z]);
    }
}

bool ConfigStore::set_sample_interval_ms(uint32_t ms) {
    if (ms < kMinSampleIntervalMs || ms > kMaxSampleIntervalMs) return false;
    settings_.sample_interval_ms = ms;
    save_settings();
    return true;
}

bool ConfigStore::set_zone_name(uint8_t zone, const std::string& name) {
    if (zone >= kZoneCount || name.empty() || name.size() > kMaxZoneNameLen) {
        return false;
    }
    settings_.zone_names[zone] = name;
    save_settings();
    return true;
}

bool ConfigStore::create_pair_request(PairRequest* out) {
    if (pending_.active) return false;  // one active request at a time
    uint8_t rnd[9] = {0};
    secrets_->random_bytes(rnd, 9);
    pending_.pair_id = hex_lower(rnd, 5);
    pending_.nonce = hex_lower(rnd + 5, 4);
    pending_.created_ms = clock_->monotonic_ms();
    pending_.active = true;
    if (out) *out = pending_;
    return true;
}

bool ConfigStore::confirm_pair_request(const std::string& pair_id,
                                       PairingToken* out) {
    if (!pending_.active || pending_.pair_id != pair_id) return false;
    uint8_t rnd[16] = {0};
    secrets_->random_bytes(rnd, 16);
    PairingToken t;
    t.token = hex_lower(rnd, 16);
    t.label = "app";
    t.created_ms = clock_->monotonic_ms();
    tokens_.push_back(t);
    std::string raw;
    for (const auto& tok : tokens_) {
        if (!raw.empty()) raw += ";";
        raw += tok.label + "|" + tok.token;
    }
    kv_->put("pair_tokens", raw);
    pending_.active = false;
    if (out) *out = t;
    return true;
}

bool ConfigStore::revoke(const std::string& token) {
    for (size_t i = 0; i < tokens_.size(); i++) {
        if (tokens_[i].token == token) {
            tokens_.erase(tokens_.begin() + i);
            std::string raw;
            for (const auto& tok : tokens_) {
                if (!raw.empty()) raw += ";";
                raw += tok.label + "|" + tok.token;
            }
            kv_->put("pair_tokens", raw);
            return true;
        }
    }
    return false;
}

bool ConfigStore::authorize(const std::string& maybe_token) const {
    if (maybe_token.size() != 32) return false;
    bool found = false;
    for (const auto& t : tokens_) {
        bool match = t.token.size() == maybe_token.size();
        for (size_t i = 0; i < t.token.size(); i++) {
            match &= (t.token[i] == maybe_token[i]);  // branch-symmetric
        }
        found |= match;
    }
    return found;
}

void ConfigStore::reset_all() {
    kv_->remove("pair_tokens");
    kv_->remove("interval_ms");
    for (int z = 0; z < kZoneCount; z++) {
        kv_->remove("zone_name_" + std::to_string(z));
    }
    tokens_.clear();
    pending_.active = false;
    settings_ = Settings{};
}

}  // namespace pp
