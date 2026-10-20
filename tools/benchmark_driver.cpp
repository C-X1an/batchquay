// Measurement harness: the production decoder and actor are linked unchanged.
#include "scheduler.hpp"
#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <psapi.h>
#else
#include <sys/resource.h>
#endif

namespace {
using Clock=std::chrono::steady_clock;
double ms(Clock::time_point start) {
  return std::chrono::duration<double,std::milli>(Clock::now()-start).count();
}
std::size_t peak_rss() {
#ifdef _WIN32
  PROCESS_MEMORY_COUNTERS info{};
  if (!GetProcessMemoryInfo(GetCurrentProcess(),&info,sizeof(info))) throw bq::Error("E_INTERNAL");
  return static_cast<std::size_t>(info.PeakWorkingSetSize);
#else
  rusage info{};
  if (getrusage(RUSAGE_SELF,&info)!=0) throw bq::Error("E_INTERNAL");
  return static_cast<std::size_t>(info.ru_maxrss)*1024;
#endif
}
struct Request {
  std::vector<std::uint32_t> prompt,output;
  std::size_t limit{},cursor{},resident{};
  std::vector<float> logits;
  std::unique_ptr<bq::ContiguousCache> cache;
  std::vector<double> observed;
};
void emit_token(Request &r,std::uint32_t token,double timestamp) {
  r.output.push_back(token);r.observed.push_back(timestamp);
}
}
int main(int argc,char **argv) {
  try {
    if(argc!=3) throw bq::Error("E_FORMAT");
    const std::string variant=argv[1];
    if(variant!="paged" && variant!="contiguous" && variant!="serial-recompute") throw bq::Error("E_FORMAT");
    const auto load_start=Clock::now();
    const auto model=bq::Model::load(argv[2]);
    const auto load_ms=ms(load_start);
    std::size_t count{};
    if(!(std::cin>>count) || count==0 || count>16) throw bq::Error("E_LIMIT");
    std::vector<Request> requests(count);
    std::size_t pages=0;
    for(auto &r:requests) {
      std::size_t length{};
      if(!(std::cin>>length>>r.limit) || length==0 || length>256 || r.limit==0 ||
         length>model.cfg.positions || r.limit>model.cfg.positions-length) throw bq::Error("E_LIMIT");
      r.prompt.resize(length);
      for(auto &token:r.prompt)
        if(!(std::cin>>token) || token>=model.cfg.vocab) throw bq::Error("E_TOKEN");
      pages+=(length+r.limit+3)/4;
    }
    std::string extra;
    if(std::cin>>extra) throw bq::Error("E_FORMAT");
    const auto token_bytes=static_cast<std::size_t>(model.cfg.layers)*2*model.cfg.kv_dim()*sizeof(float);
    std::size_t peak_logical=0,peak_allocated=0,peak_pages=0,rounds=0;
    const auto start=Clock::now(); // Simultaneous arrival, before admission/cache allocation.
    if(variant=="paged") {
      bq::Scheduler actor(model,"measurement",pages,4,count,4);
      for(std::size_t i=0;i<count;++i)
        (void)actor.submit("benchmark",std::to_string(i),requests[i].prompt,requests[i].limit);
      while(actor.live()) {
        const auto events=actor.step();
        const auto timestamp=ms(start); // Entire STEP is visible atomically to the controller.
        ++rounds;
        for(const auto &event:events) {
          auto &r=requests.at(static_cast<std::size_t>(std::stoul(event.id)));
          if(event.event=="prefill") r.resident=event.index;
          if(event.event=="token") {
            emit_token(r,event.token,timestamp);
            if(r.output.size()<r.limit) ++r.resident;
          }
          if(event.event=="finished") r.resident=0;
          if(event.event=="failed") throw bq::Error(event.code);
        }
        std::size_t logical=0;
        for(const auto &r:requests) logical+=r.resident;
        peak_logical=std::max(peak_logical,logical*token_bytes);
        peak_pages=std::max(peak_pages,actor.physical());
      }
      peak_pages=actor.peak_physical();
      peak_logical=actor.peak_cached_tokens()*token_bytes;
      peak_allocated=actor.allocated_payload_bytes();
      if(actor.reserved()!=0 || actor.physical()!=0) throw bq::Error("E_INTERNAL");
    } else {
      if(variant=="contiguous") {
        for(auto &r:requests) r.cache=std::make_unique<bq::ContiguousCache>(model.cfg);
        peak_allocated=count*model.cfg.positions*token_bytes;
      }
      auto forward=[&](Request &r,std::uint32_t token,std::size_t position) {
        if(r.cache) {
          auto result=bq::forward(model,*r.cache,token,position);
          r.resident=position+1;
          std::size_t logical=0;for(const auto &request:requests) logical+=request.resident;
          peak_logical=std::max(peak_logical,logical*token_bytes);
          return result;
        }
        // No KV reuse: independently recompute every prefix for each consumed token.
        bq::ContiguousCache temporary(model.cfg);
        std::vector<float> result;
        for(std::size_t p=0;p<=position;++p) {
          const auto input=p<r.prompt.size() ? r.prompt[p] : r.output[p-r.prompt.size()];
          result=bq::forward(model,temporary,input,p);
        }
        peak_allocated=std::max(peak_allocated,static_cast<std::size_t>(model.cfg.positions)*token_bytes);
        peak_logical=std::max(peak_logical,(position+1)*token_bytes);
        return result;
      };
      for(bool live=true;live;) {
        live=false;
        std::vector<std::pair<std::size_t,std::uint32_t>> pending;
        for(std::size_t i=0;i<count;++i) {
          auto &r=requests[i];
          if(r.output.size()==r.limit) continue;
          live=true;
          if(r.cursor<r.prompt.size()) {
            const auto stop=std::min(r.prompt.size(),r.cursor+4);
            while(r.cursor<stop) {
              r.logits=forward(r,r.prompt[r.cursor],r.cursor);++r.cursor;
            }
            r.resident=r.cursor;
          } else {
            const auto token=bq::greedy(r.logits);
            // Append only after next-state computation succeeds, as in the actor.
            if(r.output.size()+1<r.limit) {
              // Recompute needs the new token in its prefix but must not publish it yet.
              r.output.push_back(token);
              r.logits=forward(r,token,r.prompt.size()+r.output.size()-1);
              r.output.pop_back();
            }
            pending.emplace_back(i,token);
            if(r.output.size()+1==r.limit) {r.resident=0;r.cache.reset();}
          }
        }
        if(!live) break;
        const auto timestamp=ms(start);++rounds;
        for(const auto &[i,token]:pending) {
          auto &r=requests[i];emit_token(r,token,timestamp);
          if(r.output.size()==r.limit) {r.resident=0;r.cache.reset();}
        }
        if(variant=="contiguous") {
          std::size_t logical=0;for(const auto &r:requests) logical+=r.resident;
          peak_logical=std::max(peak_logical,logical*token_bytes);
        }
      }
    }
    const auto elapsed=ms(start);
    std::cout<<std::setprecision(12)<<"{\"variant\":\""<<variant<<"\",\"load_ms\":"<<load_ms
      <<",\"elapsed_ms\":"<<elapsed<<",\"peak_rss_bytes\":"<<peak_rss()
      <<",\"logical_cache_bytes\":"<<peak_logical<<",\"allocated_kv_bytes\":"<<peak_allocated
      <<",\"peak_owned_pages\":"<<peak_pages<<",\"reserved_page_bound\":"<<pages
      <<",\"rounds\":"<<rounds<<",\"requests\":[";
    for(std::size_t i=0;i<count;++i) {
      if(i) std::cout<<',';
      const auto &r=requests[i];
      if(r.output.size()!=r.limit || r.observed.size()!=r.limit) throw bq::Error("E_INTERNAL");
      std::cout<<"{\"ttft_ms\":"<<r.observed.front()<<",\"output\":[";
      for(std::size_t j=0;j<r.output.size();++j) {if(j)std::cout<<',';std::cout<<r.output[j];}
      std::cout<<"],\"token_observed_ms\":[";
      for(std::size_t j=0;j<r.observed.size();++j) {if(j)std::cout<<',';std::cout<<r.observed[j];}
      std::cout<<"]}";
    }
    std::cout<<"]}\n";
  } catch(const std::exception &error) {std::cerr<<error.what()<<'\n';return 2;}
}
