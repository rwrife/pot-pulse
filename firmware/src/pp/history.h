// Bounded on-device history ring (architecture R-07: retention must be finite).
#pragma once

#include <vector>

#include "pp/model.h"

namespace pp {

class History {
  public:
    explicit History(int capacity = kHistoryCapacity)
        : cap_(capacity), items_(capacity) {}

    void append(const MoistureSample& s);  // evicts oldest when full
    int size() const { return count_; }
    int capacity() const { return cap_; }

    // Newest-first bounded page matching GET /api/v1/history semantics.
    // from/to filter on wall_ms when synchronized; samples without wall time
    // are only included when the filter window is open.
    std::vector<MoistureSample> page(const std::string& zone_id,
                                     int64_t from_ms, int64_t to_ms,
                                     int limit) const;

    // Oldest-first snapshot of everything retained (export/backup).
    std::vector<MoistureSample> all() const;

    // DELETE /api/v1/history semantics: returns number deleted.
    int clear();

  private:
    int cap_;
    std::vector<MoistureSample> items_;
    int head = 0;    // next write slot
    int count_ = 0;  // valid entries

    const MoistureSample* at_index(int logical) const;  // 0 = oldest
};

}  // namespace pp
