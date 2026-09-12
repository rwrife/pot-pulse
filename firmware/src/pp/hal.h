// Pot Pulse firmware portable core — HAL interfaces.
// Implemented by the device layer (main.cpp) and by fakes in native tests.
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace pp {

// Minimal blocking I2C (7-bit address, no clock-stretch surprises beyond the
// Arduino Wire timeout). Returns false on NACK/bus error.
struct II2c {
    virtual ~II2c() = default;
    virtual bool write_read(uint8_t addr, const uint8_t* wr, size_t wr_len,
                            uint8_t* rd, size_t rd_len) = 0;
};

struct IClock {
    virtual ~IClock() = default;
    virtual uint64_t monotonic_ms() const = 0;
    virtual int64_t wall_ms() const = 0;  // -1 while unsynchronized
};

struct ISecrets {
    virtual ~ISecrets() = default;
    // Stable per-device identifier (derived from MAC on device, fixed in tests).
    virtual std::string device_id() const = 0;
    // Raw 16-byte random for token generation.
    virtual void random_bytes(uint8_t* out, size_t n) = 0;
};

}  // namespace pp
