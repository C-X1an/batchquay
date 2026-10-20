#include "cache.hpp"
#include <algorithm>
#include <limits>
#include <utility>

namespace bq {
Arena::Arena(std::size_t pages,std::size_t elements):elements_(elements) {
  if (pages==0 || pages>4096 || elements==0 || elements>(1ULL<<26) || pages>(1ULL<<26)/elements)
    throw Error("E_LIMIT");
  pages_.resize(pages);
}
Arena::Page &Arena::check(PageHandle h,const Owner &owner) {
  return const_cast<Page &>(std::as_const(*this).check(h,owner));
}
const Arena::Page &Arena::check(PageHandle h,const Owner &owner) const {
  if (h.index>=pages_.size()) throw Error("E_STALE");
  const auto &p=pages_[h.index];
  if (!p.owner || p.epoch!=h.epoch) throw Error("E_STALE");
  if (*p.owner!=owner) throw Error("E_OWNER"); // MUTATION_GUARD_OWNER
  return p;
}
PageHandle Arena::allocate(const Owner &owner) {
  for (std::size_t i=0;i<pages_.size();++i) {
    auto &p=pages_[i];
    if (!p.owner) {
      if (p.epoch==std::numeric_limits<std::uint64_t>::max()) throw Error("E_LIMIT");
      p.data.assign(elements_,0.0F); // clear before publishing new ownership
      p.owner=owner; ++p.epoch; ++used_;peak_used_=std::max(peak_used_,used_);
      return {i,p.epoch};
    }
  }
  throw Error("E_CAPACITY");
}
void Arena::release(PageHandle h,const Owner &owner) {
  auto &p=check(h,owner);p.owner.reset();--used_;
}
std::size_t Arena::payload_capacity_bytes() const {
  std::size_t bytes=0;
  for(const auto &page:pages_) bytes+=page.data.capacity()*sizeof(float);
  return bytes;
}
void Arena::store(PageHandle h,const Owner &owner,std::size_t offset,
                  std::span<const float> values) {
  auto &data=check(h,owner).data;
  if (offset>data.size() || values.size()>data.size()-offset) throw Error("E_LIMIT");
  std::copy(values.begin(),values.end(),data.begin()+static_cast<std::ptrdiff_t>(offset));
}
void Arena::load(PageHandle h,const Owner &owner,std::size_t offset,std::span<float> out) const {
  const auto &data=check(h,owner).data;
  if (offset>data.size() || out.size()>data.size()-offset) throw Error("E_LIMIT");
  std::copy_n(data.begin()+static_cast<std::ptrdiff_t>(offset),out.size(),out.begin());
}
std::size_t page_elements(const Config &cfg,std::size_t page_tokens) {
  cfg.validate();
  if (page_tokens==0 || page_tokens>256) throw Error("E_LIMIT");
  const auto n=static_cast<std::size_t>(cfg.layers)*2*page_tokens*cfg.kv_dim();
  if (n>(1ULL<<26)) throw Error("E_LIMIT");
  return n;
}
PagedCache::PagedCache(Arena &arena,Owner owner,Config cfg,std::size_t page_tokens)
    :arena_(arena),owner_(std::move(owner)),cfg_(cfg),page_tokens_(page_tokens),lengths_(cfg.layers) {
  (void)page_elements(cfg,page_tokens);
  pages_.reserve((cfg.positions+page_tokens-1)/page_tokens);
}
PagedCache::~PagedCache() {
  // Invariant failure must not be hidden. No user callback can mutate arena ownership.
  for (auto p:pages_) arena_.release(p,owner_);
}
std::size_t PagedCache::offset(std::size_t layer,std::size_t pos,bool val) const {
  if (layer>=cfg_.layers || pos>=cfg_.positions) throw Error("E_LIMIT");
  return ((layer*2+static_cast<std::size_t>(val))*page_tokens_+pos%page_tokens_)*cfg_.kv_dim();
}
void PagedCache::put(std::size_t layer,std::size_t pos,std::span<const float> k,std::span<const float> v) {
  const auto ko=offset(layer,pos,false),vo=offset(layer,pos,true);
  if (k.size()!=cfg_.kv_dim() || v.size()!=k.size() || pos!=lengths_[layer]) throw Error("E_INTERNAL");
  const auto pn=pos/page_tokens_;
  if (pn>pages_.size()) throw Error("E_INTERNAL");
  if (pn==pages_.size()) pages_.push_back(arena_.allocate(owner_));
  arena_.store(pages_[pn],owner_,ko,k);
  arena_.store(pages_[pn],owner_,vo,v);
  ++lengths_[layer];
}
void PagedCache::copy(std::size_t layer,std::size_t pos,bool val,std::span<float> out) const {
  const auto off=offset(layer,pos,val);
  if (pos>=lengths_[layer] || pos/page_tokens_>=pages_.size() || out.size()!=cfg_.kv_dim())
    throw Error("E_STALE");
  arena_.load(pages_[pos/page_tokens_],owner_,off,out);
}
void PagedCache::copy_key(std::size_t l,std::size_t p,std::span<float> out) const {
  copy(l,p,false,out);
}
void PagedCache::copy_value(std::size_t l,std::size_t p,std::span<float> out) const {
  copy(l,p,true,out);
}
} // namespace bq
