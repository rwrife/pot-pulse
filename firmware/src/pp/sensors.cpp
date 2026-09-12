#include "pp/sensors.h"

#include <cmath>

namespace pp {

// ---------------- SHT40 ----------------

uint8_t Sht40::crc8(const uint8_t* data, size_t n) {
    // Sensirion SHT4x DS v6.4 §4.4 Table 7: poly 0x31, init 0xFF,
    // no reflection, final XOR 0x00.
    uint8_t crc = 0xFF;
    for (size_t i = 0; i < n; i++) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; bit++) {
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x31)
                               : (uint8_t)(crc << 1);
        }
    }
    return crc;
}

bool Sht40::read(float* temperature_c, float* humidity_rh) {
    const uint8_t cmd = 0xFD;  // high-repeatability T&RH (DS §4.5)
    uint8_t rx[6] = {0};
    // Clock stretching covers the ~8.2 ms conversion on normal I2C masters;
    // Wire has a bus timeout so a stuck bus fails the transfer (R-04).
    if (!i2c_->write_read(kAddr, &cmd, 1, rx, 6)) return false;
    if (crc8(rx, 2) != rx[2] || crc8(rx + 3, 2) != rx[5]) return false;
    const uint32_t st = (uint32_t(rx[0]) << 8) | rx[1];
    const uint32_t srh = (uint32_t(rx[3]) << 8) | rx[4];
    // DS §4.6 eq (2) and eq (1); RH cropped to physical 0..100 %RH range.
    *temperature_c = -45.0f + 175.0f * float(st) / 65535.0f;
    float rh = -6.0f + 125.0f * float(srh) / 65535.0f;
    if (rh < 0.0f) rh = 0.0f;
    if (rh > 100.0f) rh = 100.0f;
    *humidity_rh = rh;
    return true;
}

// ---------------- VEML7700 ----------------

bool Veml7700::write_reg(uint8_t reg, uint16_t value) {
    // Datasheet "COMMAND REGISTER FORMAT": write command code, then LSB, MSB.
    const uint8_t tx[3] = {reg, uint8_t(value & 0xFF), uint8_t(value >> 8)};
    return i2c_->write_read(kAddr, tx, 3, nullptr, 0);
}

bool Veml7700::read_reg(uint8_t reg, uint16_t* value) {
    const uint8_t ptr = reg;  // CRUD mode: pointer write, then read 16-bit LE
    uint8_t rx[2] = {0, 0};
    if (!i2c_->write_read(kAddr, &ptr, 1, rx, 2)) return false;
    *value = uint16_t(rx[0]) | (uint16_t(rx[1]) << 8);
    return true;
}

bool Veml7700::begin() {
    // ALS_CONF_0 (0x00): gain x1 (00b), IT 100 ms (0000b), persistence 1,
    // interrupt disabled, ALS_SD=0 (power on). Datasheet default is shut
    // down ("command code 0 default value is 01"), so this write is required.
    return write_reg(0x00, 0x0000);
}

float Veml7700::lux_from_counts(uint16_t counts, uint8_t gain_bits,
                                uint16_t it_ms) {
    // Vishay AN 84323 (Rev 06-Mar-2025) resolution table:
    // scale = 0.0042 lx/count at gain x2, IT 800 ms; halves per gain step,
    // scales with integration time.
    float gain_mult;
    switch (gain_bits) {
        case 0b00: gain_mult = 1.0f; break;
        case 0b01: gain_mult = 2.0f; break;
        case 0b10: gain_mult = 0.125f; break;
        default: gain_mult = 0.25f; break;  // 0b11
    }
    if (it_ms == 0) it_ms = 100;
    float scale = 0.0042f * (2.0f / gain_mult) * (800.0f / float(it_ms));
    float lux = float(counts) * scale;
    // AN 84323 linearity correction for >1000 lx (worked example verified
    // in unit tests: 5581 counts gain x1/4 IT 100 ms -> 1658 lx corrected).
    if (lux > 1000.0f) {
        const double l = lux;
        lux = float(6.0135e-13 * l * l * l * l - 9.3924e-9 * l * l * l +
                    8.1488e-5 * l * l + 1.0023 * l);
    }
    return lux;
}

bool Veml7700::read_lux(float* lux) {
    uint16_t als = 0;
    if (!read_reg(0x04, &als)) return false;  // ALS result register
    // This firmware always configures gain x1 / IT 100 ms (begin()).
    *lux = lux_from_counts(als, 0b00, 100);
    return true;
}

// ---------------- ADS1115 ----------------

bool Ads1115::write_reg(uint8_t reg, uint16_t value) {
    // Big-endian 16-bit register access via pointer byte (DS §8.1.1).
    const uint8_t tx[3] = {reg, uint8_t(value >> 8), uint8_t(value & 0xFF)};
    return i2c_->write_read(kAddr, tx, 3, nullptr, 0);
}

bool Ads1115::read_reg(uint8_t reg, uint16_t* value) {
    const uint8_t ptr = reg;
    uint8_t rx[2] = {0, 0};
    if (!i2c_->write_read(kAddr, &ptr, 1, rx, 2)) return false;
    *value = (uint16_t(rx[0]) << 8) | rx[1];
    return true;
}

bool Ads1115::begin() {
    // Write the documented power-on value, then confirm it reads back —
    // a mismatch means the part is absent, unpowered, or bus-stuck.
    if (!write_reg(0x01, kResetConfig)) return false;
    uint16_t cfg = 0;
    if (!read_reg(0x01, &cfg)) return false;
    return cfg == kResetConfig;
}

bool Ads1115::read_channel(uint8_t ain, int32_t* counts) {
    if (ain > 3) return false;
    // Single-ended AINn vs GND (MUX=100b|n), PGA 001 = ±4.096 V — chosen so
    // the SEN0193 analog output (documented up to 3.0 V at 3.3 V supply)
    // never clips, trading LSB size that is irrelevant for moisture
    // (125 µV/LSB). MODE single-shot bit8=1, DR 100b = 128 SPS,
    // comparator disabled (DS §8.1.3 Table 8-3).
    const uint16_t cfg = uint16_t(0x8000u | ((0x4u + ain) << 12) |
                                  (0x1u << 9) | 0x0100u | 0x0040u | 0x3u);
    if (!write_reg(0x01, cfg)) return false;
    // Poll OS until conversion completes (OS reads 1 when not converting);
    // bounded so a stuck device surfaces as sensor_error, never a hang.
    uint16_t readback = 0;
    for (int i = 0; i < 50; i++) {
        if (!read_reg(0x01, &readback)) return false;
        if (readback & 0x8000u) break;
    }
    if (!(readback & 0x8000u)) return false;
    uint16_t raw = 0;
    if (!read_reg(0x00, &raw)) return false;  // conversion register
    *counts = int16_t(raw);                     // two's complement
    return true;
}

}  // namespace pp
