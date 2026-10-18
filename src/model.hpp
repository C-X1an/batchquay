#pragma once
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

namespace bq {
class Error : public std::runtime_error {
public:
  explicit Error(const std::string &code) : std::runtime_error(code) {}
};
struct Config {
  std::uint32_t vocab{}, dim{}, hidden{}, layers{}, heads{}, kv_heads{}, positions{};
  float epsilon{}, theta{};
  [[nodiscard]] std::size_t head_dim() const { return dim / heads; }
  [[nodiscard]] std::size_t kv_dim() const { return kv_heads * head_dim(); }
  void validate() const;
};
struct Layer {
  std::vector<float> norm1, q, k, v, o, norm2, gate, up, down;
};
struct Model {
  Config cfg;
  std::vector<float> embedding, norm;
  std::vector<Layer> layers;
  static Model load(const std::filesystem::path &path);
};
class KVCache {
public:
  virtual ~KVCache() = default;
  virtual void put(std::size_t layer, std::size_t pos, std::span<const float> k,
                   std::span<const float> v) = 0;
  [[nodiscard]] virtual std::span<const float> key(std::size_t layer,
                                                  std::size_t pos) const = 0;
  [[nodiscard]] virtual std::span<const float> value(std::size_t layer,
                                                    std::size_t pos) const = 0;
};
class ContiguousCache final : public KVCache {
  Config cfg_;
  std::vector<float> data_;
  std::vector<std::size_t> lengths_;
  [[nodiscard]] std::size_t offset(std::size_t layer, std::size_t pos,
                                  bool val) const;
public:
  explicit ContiguousCache(Config cfg);
  void put(std::size_t layer, std::size_t pos, std::span<const float> k,
           std::span<const float> v) override;
  [[nodiscard]] std::span<const float> key(std::size_t layer,
                                          std::size_t pos) const override;
  [[nodiscard]] std::span<const float> value(std::size_t layer,
                                            std::size_t pos) const override;
};
[[nodiscard]] std::vector<float> forward(const Model &model, KVCache &cache,
                                         std::uint32_t token, std::size_t pos);
[[nodiscard]] std::uint32_t greedy(std::span<const float> logits);
} // namespace bq
