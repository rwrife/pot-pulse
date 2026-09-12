// Sensor drivers, datasheet-validated (see citations inline).
//
// Evidence boundary: static datasheet transcription + host unit tests over
// fake I2C. No bench verification of real parts is claimed.
#pragma once

#include "pp/hal.h"
#include "pp/model.h"

namespace pp {

// ---------- SHT40 (Sensirion SHT4x datasheet D1 v6.4) ----------
//
// Datasheet citations (sensirion.com/media/documents/33FD6951/6555C40E/...pdf):
//  - Table 4 / section 4.5: command 0xFD = measure T&RH high repeatability,
//    response 6 bytes [T_MSB,T_LSB,T_CRC,RH_MSB,RH_LSB,RH_CRC], max 8.2 ms.
//  - Section 4.4 Table 7: CRC-8 poly 0x31 (x^8+x^5+x^4+1), init 0xFF,
//    reflect false/false, final XOR 0x00. Worked example CRC(0xBEEF)=0x92.
//  - Section 4.6 eq (1)/(2):
//      RH% = -6 + 125 * S_RH / (2^16 - 1)
//      T   = -45 + 175 * S_T  / (2^16 - 1)
//  - Address 0x44 fixed for SHT40-AD1B (selection doc §3).
//  - Section 4.8: soft reset command 0x94.
class Sht40 {
  public:
    static constexpr uint8_t kAddr = 0x44;
    explicit Sht40(II2c* i2c) : i2c_(i2c) {}

    static uint8_t crc8(const uint8_t* data, size_t n);  // poly 0x31 init 0xFF

    bool read(float* temperature_c, float* humidity_rh);

  private:
    II2c* i2c_;
};

// ---------- VEML7700 (Vishay Rev. 1.8 + design note 84323 Rev 06-Mar-2025) --
//
// Datasheet citations (vishay.com/docs/84286/veml7700.pdf):
//  - "COMMAND REGISTER FORMAT": command codes ALS_CONF_0=0x00, ALS=0x04.
//    Datasheet default note: config default 01 = device shut down — firmware
//    must power it on.
//  - Table 1 (Config 0x00): ALS_GAIN bits 12:11 (00=×1, 01=×2, 10=×1/8,
//    11=×1/4), ALS_IT bits 9:6 (1100=25ms ... 0011=800ms), ALS_SD bit 0.
//  - Design note AN VISHAY84323 resolution table: lux scale factor per
//    (gain × IT) = 0.0042·(2/gain_mult)·(800/IT_ms) lx/count, e.g.
//    gain×1/IT100ms → 0.5376 lx/count; gain×1/IT800ms → 0.0672.
//    Worked example (p.5): 5581 counts × 0.2688 (gain 1/4, IT 100 ms) = 1500 lx.
//  - >1000 lx linearity correction polynomial from the design note.
class Veml7700 {
  public:
    static constexpr uint8_t kAddr = 0x10;
    explicit Veml7700(II2c* i2c) : i2c_(i2c) {}

    // Configures ALS: gain ×1, IT 100 ms, interrupt disabled, powered on.
    bool begin();
    bool read_lux(float* lux);

    static float lux_from_counts(uint16_t counts, uint8_t gain_bits,
                                 uint16_t it_ms);

  private:
    bool write_reg(uint8_t reg, uint16_t value);
    bool read_reg(uint8_t reg, uint16_t* value);
    II2c* i2c_;
};

// ---------- ADS1115 (TI SBAS474M, 2024) ----------
//
// Datasheet citations (ti.com/lit/ds/symlink/ads1115.pdf):
//  - §8.1.1 Pointer register: 0x00 conv, 0x01 config, 0x02 lo_thresh,
//    0x03 hi_thresh (16-bit big-endian values).
//  - §8.1.3 Table 8-3 Config: OS bit15 (1=not converting; write 1 to start
//    single conversion), MUX[2:0] bits14:12 — 100b..111b = AINP=AINn,
//    AINN=GND (single-ended), PGA[2:0] bits11:9 (010 = ±2.048 V full scale),
//    MODE bit8 (1=single-shot), DR bits6:4 (100 = 128 SPS),
//    COMP_QUE bits1:0 (11 = comparator disabled).
//  - Reset value 0x8583 documented at §8.1.3 header — asserted in tests.
//  - Conversion register read returns two's-complement counts.
class Ads1115 {
  public:
    static constexpr uint8_t kAddr = 0x48;  // ADDR tied to GND (selection doc)
    static constexpr uint16_t kResetConfig = 0x8583;
    explicit Ads1115(II2c* i2c) : i2c_(i2c) {}

    bool begin();                      // verify/reset config register
    bool read_channel(uint8_t ain, int32_t* counts);  // ain = 0..3

  private:
    bool write_reg(uint8_t reg, uint16_t value);
    bool read_reg(uint8_t reg, uint16_t* value);
    II2c* i2c_;
};

}  // namespace pp
