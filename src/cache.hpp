#pragma once
#include "model.hpp"
#include <optional>
#include <compare>

namespace bq {
struct Owner {
  std::string session, subject, request;
  std::uint64_t generation{};
  bool operator==(const Owner &) const = default;
};
struct PageHandle { std::size_t index{}; std::uint64_t epoch{}; };
class Arena {
  struct Page {
    std::optional<Owner> owner;
    std::uint64_t epoch{};
    std::vector<float> data;
  };
  std::vector<Page> pages_;
  std::size_t elements_, used_=0;
  Page &check(PageHandle h,const Owner &owner);
  const Page &check(PageHandle h,const Owner &owner) const;
public:
  Arena(std::size_t pages,std::size_t elements);
  Arena(const Arena &)=delete;
  Arena &operator=(const Arena &)=delete;
  PageHandle allocate(const Owner &owner);
  void release(PageHandle h,const Owner &owner);
  [[nodiscard]] std::span<float> write(PageHandle h,const Owner &owner);
  [[nodiscard]] std::span<const float> read(PageHandle h,const Owner &owner) const;
  [[nodiscard]] std::size_t used() const { return used_; }
  [[nodiscard]] std::size_t capacity() const { return pages_.size(); }
};
class PagedCache final : public KVCache {
  Arena &arena_;
  Owner owner_;
  Config cfg_;
  std::size_t page_tokens_;
  std::vector<PageHandle> pages_;
  std::vector<std::size_t> lengths_;
  [[nodiscard]] std::size_t offset(std::size_t layer,std::size_t pos,bool val) const;
  [[nodiscard]] std::span<const float> get(std::size_t layer,std::size_t pos,bool val) const;
public:
  PagedCache(Arena &arena,Owner owner,Config cfg,std::size_t page_tokens);
  ~PagedCache() override;
  PagedCache(const PagedCache &)=delete;
  PagedCache &operator=(const PagedCache &)=delete;
  void put(std::size_t layer,std::size_t pos,std::span<const float> k,std::span<const float> v) override;
  [[nodiscard]] std::span<const float> key(std::size_t layer,std::size_t pos) const override;
  [[nodiscard]] std::span<const float> value(std::size_t layer,std::size_t pos) const override;
};
[[nodiscard]] std::size_t page_elements(const Config &cfg,std::size_t page_tokens);
} // namespace bq
