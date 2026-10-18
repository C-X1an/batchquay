#include "model.hpp"
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <fstream>
#include <limits>
#include <numeric>

namespace bq {
namespace {
constexpr std::uint64_t MAX_FILE = 1ULL << 30;
std::uint32_t u32(std::istream &in) {
  std::array<unsigned char, 4> bytes{};
  if (!in.read(reinterpret_cast<char *>(bytes.data()), 4)) throw Error("E_MODEL");
  return static_cast<std::uint32_t>(bytes[0]) |
         (static_cast<std::uint32_t>(bytes[1]) << 8U) |
         (static_cast<std::uint32_t>(bytes[2]) << 16U) |
         (static_cast<std::uint32_t>(bytes[3]) << 24U);
}
float f32(std::istream &in) { return std::bit_cast<float>(u32(in)); }
std::vector<float> read_tensor(std::istream &in, std::size_t count) {
  std::vector<float> result(count);
  if constexpr (std::endian::native == std::endian::little) {
    if (!in.read(reinterpret_cast<char *>(result.data()),
                 static_cast<std::streamsize>(count * sizeof(float))))
      throw Error("E_MODEL");
  } else {
    for (auto &x : result) x = f32(in);
  }
  for (float x : result) if (!std::isfinite(x)) throw Error("E_MODEL");
  return result;
}
std::vector<float> matvec(std::span<const float> w, std::span<const float> x,
                          std::size_t rows) {
  if (w.size() != rows * x.size()) throw Error("E_INTERNAL");
  std::vector<float> y(rows);
  for (std::size_t i = 0; i < rows; ++i) {
    double sum = 0;
    for (std::size_t j = 0; j < x.size(); ++j)
      sum += static_cast<double>(w[i * x.size() + j]) * x[j];
    y[i] = static_cast<float>(sum);
    if (!std::isfinite(y[i])) throw Error("E_NUMERIC");
  }
  return y;
}
std::vector<float> rms(std::span<const float> x, std::span<const float> weight,
                       float eps) {
  double sum = 0;
  for (float t : x) sum += static_cast<double>(t) * t;
  const double scale = 1.0 / std::sqrt(sum / static_cast<double>(x.size()) + eps);
  std::vector<float> y(x.size());
  for (std::size_t i = 0; i < x.size(); ++i)
    y[i] = static_cast<float>(x[i] * scale * weight[i]);
  return y;
}
void rotate(std::vector<float> &x, std::size_t heads, std::size_t hd,
            std::size_t pos, float theta) {
  for (std::size_t h = 0; h < heads; ++h)
    for (std::size_t i = 0; i < hd / 2; ++i) {
      const double angle = static_cast<double>(pos) /
          std::pow(static_cast<double>(theta), 2.0 * static_cast<double>(i) /
                                                 static_cast<double>(hd));
      const double c = std::cos(angle), s = std::sin(angle);
      const float a = x[h * hd + i], b = x[h * hd + i + hd / 2];
      x[h * hd + i] = static_cast<float>(a * c - b * s);
      x[h * hd + i + hd / 2] = static_cast<float>(b * c + a * s);
    }
}
void add(std::vector<float> &a, std::span<const float> b) {
  if (a.size() != b.size()) throw Error("E_INTERNAL");
  for (std::size_t i = 0; i < a.size(); ++i) {
    a[i] += b[i];
    if (!std::isfinite(a[i])) throw Error("E_NUMERIC");
  }
}
} // namespace

void Config::validate() const {
  if (vocab == 0 || vocab > 65536 || dim == 0 || dim > 2048 || hidden == 0 ||
      hidden > 8192 || layers == 0 || layers > 64 || heads == 0 || heads > 32 ||
      kv_heads == 0 || kv_heads > 32 || kv_heads > heads || dim % heads != 0 || heads % kv_heads != 0 ||
      (dim / heads) % 2 != 0 || positions == 0 || positions > 256 ||
      !std::isfinite(epsilon) || epsilon <= 0 || !std::isfinite(theta) || theta <= 0)
    throw Error("E_MODEL");
}
Model Model::load(const std::filesystem::path &path) {
  // Open first and size the same stream. Never trust path metadata for allocations.
  std::ifstream in(path, std::ios::binary | std::ios::ate);
  if (!in) throw Error("E_MODEL");
  const auto end = in.tellg();
  if (end < 44 || static_cast<std::uint64_t>(end) > MAX_FILE) throw Error("E_MODEL");
  in.seekg(0);
  std::array<char, 4> magic{};
  in.read(magic.data(), 4);
  if (magic != std::array<char, 4>{'B','Q','W','1'} || u32(in) != 1) throw Error("E_VERSION");
  Model m;
  auto &c = m.cfg;
  c.vocab=u32(in); c.dim=u32(in); c.hidden=u32(in); c.layers=u32(in);
  c.heads=u32(in); c.kv_heads=u32(in); c.positions=u32(in);
  c.epsilon=f32(in); c.theta=f32(in); c.validate();
  const std::uint64_t d=c.dim, f=c.hidden, kv=c.kv_dim();
  const std::uint64_t per = 2*d + 2*d*d + 2*kv*d + 3*f*d;
  const std::uint64_t count = static_cast<std::uint64_t>(c.vocab)*d + c.layers*per + d;
  if (count > (MAX_FILE-44)/4 || 44 + 4*count != static_cast<std::uint64_t>(end))
    throw Error("E_MODEL");
  m.embedding = read_tensor(in, static_cast<std::size_t>(c.vocab)*c.dim);
  for (std::size_t i=0; i<c.layers; ++i) {
    Layer l;
    l.norm1=read_tensor(in,c.dim); l.q=read_tensor(in,c.dim*c.dim);
    l.k=read_tensor(in,c.kv_dim()*c.dim); l.v=read_tensor(in,c.kv_dim()*c.dim);
    l.o=read_tensor(in,c.dim*c.dim); l.norm2=read_tensor(in,c.dim);
    l.gate=read_tensor(in,c.hidden*c.dim); l.up=read_tensor(in,c.hidden*c.dim);
    l.down=read_tensor(in,c.dim*c.hidden); m.layers.push_back(std::move(l));
  }
  m.norm=read_tensor(in,c.dim);
  if (in.peek() != std::char_traits<char>::eof()) throw Error("E_MODEL");
  return m;
}
ContiguousCache::ContiguousCache(Config cfg) : cfg_(cfg) {
  cfg.validate();
  const std::size_t n=static_cast<std::size_t>(cfg.layers)*2*cfg.positions*cfg.kv_dim();
  if (n > (1ULL<<26)) throw Error("E_LIMIT");
  data_.resize(n); lengths_.resize(cfg.layers);
}
std::size_t ContiguousCache::offset(std::size_t layer,std::size_t pos,bool val) const {
  if (layer>=cfg_.layers || pos>=cfg_.positions) throw Error("E_LIMIT");
  return ((layer*2+static_cast<std::size_t>(val))*cfg_.positions+pos)*cfg_.kv_dim();
}
void ContiguousCache::put(std::size_t layer,std::size_t pos,std::span<const float> k,
                         std::span<const float> v) {
  const auto ko=offset(layer,pos,false), vo=offset(layer,pos,true);
  if (k.size()!=cfg_.kv_dim() || v.size()!=k.size() || pos!=lengths_[layer]) throw Error("E_INTERNAL");
  std::copy(k.begin(),k.end(),data_.begin()+static_cast<std::ptrdiff_t>(ko));
  std::copy(v.begin(),v.end(),data_.begin()+static_cast<std::ptrdiff_t>(vo));
  ++lengths_[layer];
}
std::span<const float> ContiguousCache::key(std::size_t layer,std::size_t pos) const {
  const auto o=offset(layer,pos,false);
  if (pos>=lengths_[layer]) throw Error("E_STALE");
  return std::span<const float>(data_).subspan(o,cfg_.kv_dim());
}
std::span<const float> ContiguousCache::value(std::size_t layer,std::size_t pos) const {
  const auto o=offset(layer,pos,true);
  if (pos>=lengths_[layer]) throw Error("E_STALE");
  return std::span<const float>(data_).subspan(o,cfg_.kv_dim());
}
std::vector<float> forward(const Model &m, KVCache &cache,std::uint32_t token,std::size_t pos) {
  const auto &c=m.cfg;
  c.validate();
  const auto group = c.heads / c.kv_heads;
  if (group == 0) throw Error("E_MODEL");
  if (token>=c.vocab) throw Error("E_TOKEN");
  if (pos>=c.positions) throw Error("E_LIMIT");
  std::vector<float> x(m.embedding.begin()+static_cast<std::ptrdiff_t>(token*c.dim),
                       m.embedding.begin()+static_cast<std::ptrdiff_t>((token+1)*c.dim));
  const auto hd=c.head_dim();
  for (std::size_t li=0; li<c.layers; ++li) {
    const auto &l=m.layers[li];
    auto nx=rms(x,l.norm1,c.epsilon);
    auto q=matvec(l.q,nx,c.dim), k=matvec(l.k,nx,c.kv_dim()), v=matvec(l.v,nx,c.kv_dim());
    rotate(q,c.heads,hd,pos,c.theta); rotate(k,c.kv_heads,hd,pos,c.theta);
    cache.put(li,pos,k,v);
    std::vector<float> att(c.dim);
    for (std::size_t h=0; h<c.heads; ++h) {
      const std::size_t kh=h/group;
      std::vector<double> scores(pos+1);
      for (std::size_t t=0; t<=pos; ++t) {
        const auto keys=cache.key(li,t);
        double sum=0;
        for (std::size_t j=0; j<hd; ++j) sum+=static_cast<double>(q[h*hd+j])*keys[kh*hd+j];
        scores[t]=sum/std::sqrt(static_cast<double>(hd));
      }
      const double peak=*std::max_element(scores.begin(),scores.end());
      double denom=0;
      for (double &a:scores) { a=std::exp(a-peak);denom+=a; }
      for (std::size_t j=0; j<hd; ++j) {
        double a=0;
        for (std::size_t t=0;t<=pos;++t) a+=scores[t]*cache.value(li,t)[kh*hd+j]/denom;
        att[h*hd+j]=static_cast<float>(a);
      }
    }
    add(x,matvec(l.o,att,c.dim));
    nx=rms(x,l.norm2,c.epsilon);
    auto gate=matvec(l.gate,nx,c.hidden), up=matvec(l.up,nx,c.hidden);
    for (std::size_t j=0;j<c.hidden;++j) {
      const double g=gate[j];
      const double sig=g>=0 ? 1/(1+std::exp(-g)) : std::exp(g)/(1+std::exp(g));
      gate[j]=static_cast<float>(g*sig*up[j]);
      if (!std::isfinite(gate[j])) throw Error("E_NUMERIC");
    }
    add(x,matvec(l.down,gate,c.dim));
  }
  return matvec(m.embedding,rms(x,m.norm,c.epsilon),c.vocab);
}
std::uint32_t greedy(std::span<const float> logits) {
  if (logits.empty()) throw Error("E_INTERNAL");
  for (float x:logits) if (!std::isfinite(x)) throw Error("E_NUMERIC");
  return static_cast<std::uint32_t>(std::max_element(logits.begin(),logits.end())-logits.begin());
}
} // namespace bq
