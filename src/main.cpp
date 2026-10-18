#include "scheduler.hpp"
#include <algorithm>
#include <charconv>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <sstream>
#include <string_view>

namespace {
using bq::Error;
std::uint64_t number(const std::string &s) {
  std::uint64_t v=0;
  const auto result=std::from_chars(s.data(),s.data()+s.size(),v);
  if (s.empty() || result.ec!=std::errc{} || result.ptr!=s.data()+s.size()) throw Error("E_FORMAT");
  return v;
}
std::vector<std::string> words(const std::string &s) {
  std::istringstream stream(s);std::vector<std::string> result;std::string t;
  while (stream>>t) {
    result.push_back(t);
    if (result.size()>264) throw Error("E_LIMIT");
  }
  return result;
}
// 1=record, 0=EOF, -1=oversize (fully drained without a growing buffer).
int bounded_line(std::istream &in,std::string &s) {
  s.clear();bool large=false;char c{};bool any=false;
  while (in.get(c)) {
    any=true;if(c=='\n') return large ? -1 : 1;
    if (s.size()<8192) s+=c;else large=true;
  }
  return any ? (large ? -1 : 1) : 0;
}
std::string session_id() {
  std::random_device rd;std::ostringstream out;
  out<<std::hex<<std::setfill('0');
  for(int i=0;i<4;++i) out<<std::setw(8)<<static_cast<std::uint32_t>(rd());
  return out.str();
}
void event_json(const bq::Event &e) {
  // All strings originate from closed enums or validated ASCII IDs.
  std::cout<<"{\"event\":\""<<e.event<<"\",\"owner\":\""<<e.owner
           <<"\",\"id\":\""<<e.id<<"\",\"generation\":"<<e.generation;
  if (e.event=="token") std::cout<<",\"token\":"<<e.token;
  if (!e.code.empty()) std::cout<<",\"code\":\""<<e.code<<"\"";
  std::cout<<",\"index\":"<<e.index<<"}";
}
void hello(const std::string &session) {
  std::cout<<"{\"event\":\"hello\",\"protocol\":1,\"session\":\""<<session<<"\"}\n"<<std::flush;
}
void serve(const bq::Model &m,int argc,char **argv) {
  const auto pt=argc==7 ? number(argv[4]) : 16ULL;
  const auto elems=bq::page_elements(m.cfg,pt);
  const auto pages=argc==7 ? number(argv[3]) : std::min<std::uint64_t>(4096,(1ULL<<26)/elems);
  const auto limit=argc==7 ? number(argv[5]) : 16ULL;
  const auto chunk=argc==7 ? number(argv[6]) : 4ULL;
  const auto session=session_id();
  bq::Scheduler scheduler(m,session,pages,pt,limit,chunk);
  hello(session);
  std::string line;
  for (;;) {
    const int state=bounded_line(std::cin,line);if(state==0) break;
    try {
      if (state<0) throw Error("E_LIMIT");
      const auto w=words(line);
      if(w.empty()) throw Error("E_FORMAT");
      if(w[0]=="HELLO") {
        if(w.size()!=2) throw Error("E_FORMAT");
        if(w[1]!="1") throw Error("E_VERSION");
        hello(session);continue;
      }
      if(w.size()<2) throw Error("E_FORMAT");
      if(w[1]!=session) throw Error("E_SESSION");
      if(w[0]=="SUBMIT") {
        if(w.size()<7) throw Error("E_FORMAT");
        const auto count=number(w[5]),output=number(w[4]);
        if(count==0 || count>256 || w.size()!=6+count) throw Error("E_FORMAT");
        std::vector<std::uint32_t> tokens;tokens.reserve(count);
        for(std::size_t i=6;i<w.size();++i) {
          const auto n=number(w[i]);if(n>=m.cfg.vocab) throw Error("E_TOKEN");
          tokens.push_back(static_cast<std::uint32_t>(n));
        }
        const auto g=scheduler.submit(w[2],w[3],std::move(tokens),output);
        std::cout<<"{\"event\":\"accepted\",\"owner\":\""<<w[2]<<"\",\"id\":\""<<w[3]
                 <<"\",\"generation\":"<<g<<"}\n";
      } else if(w[0]=="CANCEL") {
        if(w.size()!=5 || !bq::valid_id(w[2]) || !bq::valid_id(w[3])) throw Error("E_FORMAT");
        event_json(scheduler.cancel(w[2],w[3],number(w[4])));std::cout<<'\n';
      } else if(w[0]=="STEP") {
        if(w.size()!=2) throw Error("E_FORMAT");
        const auto events=scheduler.step();std::cout<<"{\"event\":\"round\",\"events\":[";
        bool first=true;for(const auto &e:events) {if(!first) std::cout<<',';event_json(e);first=false;}
        std::cout<<"]}\n";
      } else if(w[0]=="STATUS") {
        if(w.size()!=2) throw Error("E_FORMAT");
        std::cout<<"{\"event\":\"status\",\"live\":"<<scheduler.live()<<",\"reserved\":"
                 <<scheduler.reserved()<<",\"physical\":"<<scheduler.physical()
                 <<",\"capacity\":"<<scheduler.capacity()<<"}\n";
      } else throw Error("E_FORMAT");
    } catch(const Error &e) {std::cout<<"{\"event\":\"error\",\"code\":\""<<e.what()<<"\"}\n";}
    std::cout<<std::flush;
    if(!std::cout) throw Error("E_INTERNAL");
  }
}
void logits(int argc,char **argv) {
  int mi=2;bool recompute=false,paged=false;
  if(argc>2 && std::string_view(argv[2])=="--recompute") {recompute=true;++mi;}
  else if(argc>2 && std::string_view(argv[2])=="--paged") {paged=true;++mi;}
  if(argc<=mi+1 || argc-mi-1>256) throw Error("E_FORMAT");
  const auto m=bq::Model::load(argv[mi]);
  std::vector<std::uint32_t> tokens;
  for(int i=mi+1;i<argc;++i) {
    const auto v=number(argv[i]);if(v>=m.cfg.vocab) throw Error("E_TOKEN");
    tokens.push_back(static_cast<std::uint32_t>(v));
  }
  if(tokens.size()>m.cfg.positions) throw Error("E_LIMIT");
  bq::Arena arena((m.cfg.positions+15)/16,bq::page_elements(m.cfg,16));
  std::unique_ptr<bq::KVCache> cache;
  if(paged) cache=std::make_unique<bq::PagedCache>(arena,bq::Owner{"logits","local","r",1},m.cfg,16);
  else cache=std::make_unique<bq::ContiguousCache>(m.cfg);
  std::vector<std::vector<float>> result;result.reserve(tokens.size());
  for(std::size_t p=0;p<tokens.size();++p) {
    if(recompute) {
      bq::ContiguousCache tmp(m.cfg);std::vector<float> v;
      for(std::size_t t=0;t<=p;++t) v=bq::forward(m,tmp,tokens[t],t);
      result.push_back(std::move(v));
    } else result.push_back(bq::forward(m,*cache,tokens[p],p));
  }
  std::cout<<std::setprecision(9)<<"{\"logits\":[";
  for(std::size_t i=0;i<result.size();++i) {
    if(i) std::cout<<',';
    std::cout<<'[';
    for(std::size_t j=0;j<result[i].size();++j) {if(j)std::cout<<',';std::cout<<result[i][j];}
    std::cout<<']';
  }
  std::cout<<"]}\n";
}
} // namespace
int main(int argc,char **argv) {
  try {
    if(argc==2 && std::string_view(argv[1])=="--version") {
      std::cout<<"batchquay 0.1.0 protocol=1 model=1\n";return 0;
    }
    if(argc>=2 && std::string_view(argv[1])=="logits") {logits(argc,argv);return 0;}
    if((argc==3 || argc==7) && std::string_view(argv[1])=="serve") {
      const auto model=bq::Model::load(argv[2]);serve(model,argc,argv);return 0;
    }
    throw Error("E_FORMAT");
  } catch(const Error &e) {std::cerr<<e.what()<<'\n';return 2;}
    catch(const std::bad_alloc &) {std::cerr<<"E_CAPACITY\n";return 2;}
    catch(const std::exception &) {std::cerr<<"E_INTERNAL\n";return 2;}
}
