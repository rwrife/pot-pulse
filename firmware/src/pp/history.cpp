#include "pp/history.h"

namespace pp {

void History::append(const MoistureSample& s) {
    items_[head] = s;
    head = (head + 1) % cap_;
    if (count_ < cap_) count_++;
}

const MoistureSample* History::at_index(int logical) const {
    // logical 0 = oldest retained
    if (logical < 0 || logical >= count_) return nullptr;
    int start = (head - count_ + cap_) % cap_;
    return &items_[(start + logical) % cap_];
}

std::vector<MoistureSample> History::page(const std::string& zone_id,
                                          int64_t from_ms, int64_t to_ms,
                                          int limit) const {
    if (limit < 1) limit = 1;
    if (limit > 500) limit = 500;  // protocol: firmware validates max page
    std::vector<MoistureSample> out;
    for (int i = count_ - 1; i >= 0 && int(out.size()) < limit; i--) {
        const MoistureSample* s = at_index(i);
        if (!s || s->zone_id != zone_id) continue;
        if (s->wall_ms >= 0) {
            if (from_ms > 0 && s->wall_ms < from_ms) continue;
            if (to_ms > 0 && s->wall_ms > to_ms) continue;
        } else if (from_ms > 0 || to_ms > 0) {
            continue;  // time-windowed query cannot match unsynced samples
        }
        out.push_back(*s);
    }
    return out;
}

int History::clear() {
    const int n = count_;
    head = 0;
    count_ = 0;
    return n;
}

std::vector<MoistureSample> History::all() const {
    std::vector<MoistureSample> out;
    out.reserve(count_);
    for (int i = 0; i < count_; i++) {
        const MoistureSample* s = at_index(i);
        if (s) out.push_back(*s);
    }
    return out;
}

}  // namespace pp
