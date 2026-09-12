// Settings, zone metadata, pairing token, and pairing flow state —
// persisted through a small KV abstraction (Preferences on device, map in
// tests). Architecture R-06/R-07: writes are validated; corrupt or absent
// data fall back to validated defaults; secrets never leave the API.
#pragma once

#include <map>
#include <string>
#include <vector>

#include "pp/hal.h"
#include "pp/model.h"

namespace pp {

// Stable zone identifiers (never renamed by the user; zone_names below are
// display metadata only).
inline std::string zone_id(int index) { return "z" + std::to_string(index + 1); }
bool zone_index_of(const std::string& id, int* out);

// Minimal key-value store. Device: Preferences namespace "potpulse".
struct IKv {
    virtual ~IKv() = default;
    virtual std::string get(const std::string& key,
                            const std::string& fallback) const = 0;
    virtual void put(const std::string& key, const std::string& value) = 0;
    virtual void remove(const std::string& key) = 0;
};

struct Settings {
    uint32_t sample_interval_ms = 120000;  // 2 min default, bounds in model.h
    std::string zone_names[kZoneCount] = {"zone-1", "zone-2", "zone-3",
                                          "zone-4"};
};

// One active pairing grant. token is 32 lowercase hex chars.
struct PairingToken {
    std::string token;
    std::string label;
    uint64_t created_ms = 0;
};

// Nonce-based pairing (protocol.md "pairing resource frozen in #6"):
//   1. POST /api/v1/pair/request (unauthenticated, single active request,
//      no user data) -> {pair_id, nonce}
//   2. Out-of-band confirmation on the device (USB serial `pair confirm`)
//      mints the token and binds it to the request.
//   3. App stores token; sends X-PotPulse-Token on protected calls.
// A pending request without confirmation expires; unauthenticated writes
// remain impossible at every point (fail closed, architecture §7).
struct PairRequest {
    std::string pair_id;
    std::string nonce;  // 12 hex chars shown for the confirm command
    uint64_t created_ms = 0;
    bool active = false;
};

class ConfigStore {
  public:
    ConfigStore(IKv* kv, ISecrets* secrets, IClock* clock)
        : kv_(kv), secrets_(secrets), clock_(clock) {
        load();
    }

    // ---- settings (validated on set; protocol requires server-side range
    //      checks) ----
    const Settings& settings() const { return settings_; }
    bool set_sample_interval_ms(uint32_t ms);
    bool set_zone_name(uint8_t zone, const std::string& name);

    // ---- pairing ----
    const PairRequest& pending_request() const { return pending_; }
    bool create_pair_request(PairRequest* out);           // step 1
    bool confirm_pair_request(const std::string& pair_id,
                              PairingToken* out);          // step 2 (USB)
    bool revoke(const std::string& token);
    bool authorize(const std::string& maybe_token) const;  // constant-ish time
    bool paired() const { return !tokens_.empty(); }
    const std::vector<PairingToken>& tokens() const { return tokens_; }

    // ---- destructive control words (protocol: explicit confirmation) ----
    static constexpr const char* kConfirmWord = "confirm";

    // Factory reset: erase pairing, settings, calibration is cleared by the
    // caller via CalibrationStore; network credentials retained per
    // documented reset level 'full-firmware' below.
    void reset_all();  // erase pairing + settings KV keys

    static std::string hex_lower(const uint8_t* data, size_t n);

  private:
    void load();
    void save_settings();

    IKv* kv_;
    ISecrets* secrets_;
    IClock* clock_;
    Settings settings_;
    std::vector<PairingToken> tokens_;
    PairRequest pending_;
};

}  // namespace pp
