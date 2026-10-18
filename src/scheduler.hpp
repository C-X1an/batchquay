#pragma once
#include "cache.hpp"
#include <map>
#include <memory>
#include <utility>

namespace bq {
struct Event {
  std::string event, owner, id, code;
  std::uint64_t generation{};
  std::uint32_t token{};
  std::size_t index{};
};
class Scheduler {
  struct Request {
    Owner owner;
    std::vector<std::uint32_t> prompt;
    std::size_t limit{}, cursor{}, generated{}, reservation{};
    std::vector<float> logits;
    std::unique_ptr<PagedCache> cache;
  };
  const Model &model_;
  std::string session_;
  std::size_t page_tokens_, live_limit_, chunk_, reserved_=0;
  std::uint64_t next_=0;
  Arena arena_;
  using Key=std::pair<std::string,std::string>;
  std::map<Key,Request> requests_;
  void erase(std::map<Key,Request>::iterator it);
public:
  Scheduler(const Model &model,std::string session,std::size_t pages,
            std::size_t page_tokens,std::size_t live_limit,std::size_t chunk);
  std::uint64_t submit(const std::string &owner,const std::string &id,
                        std::vector<std::uint32_t> tokens,std::size_t limit);
  Event cancel(const std::string &owner,const std::string &id,std::uint64_t generation);
  std::vector<Event> step();
  [[nodiscard]] std::size_t live() const { return requests_.size(); }
  [[nodiscard]] std::size_t reserved() const { return reserved_; }
  [[nodiscard]] std::size_t physical() const { return arena_.used(); }
  [[nodiscard]] std::size_t capacity() const { return arena_.capacity(); }
};
[[nodiscard]] bool valid_id(const std::string &id);
} // namespace bq
