#include "scheduler.hpp"
#include <algorithm>
#include <limits>

namespace bq {
bool valid_id(const std::string &id) {
  if (id.empty() || id.size()>64) return false;
  return std::all_of(id.begin(),id.end(),[](unsigned char c) {
    return (c>='a' && c<='z') || (c>='A' && c<='Z') ||
           (c>='0' && c<='9') || c=='_' || c=='-';
  });
}
Scheduler::Scheduler(const Model &model,std::string session,std::size_t pages,
                     std::size_t page_tokens,std::size_t live_limit,std::size_t chunk)
    :model_(model),session_(std::move(session)),page_tokens_(page_tokens),live_limit_(live_limit),
     chunk_(chunk),arena_(pages,page_elements(model.cfg,page_tokens)) {
  if (!valid_id(session_) || live_limit==0 || live_limit>16 || chunk==0 || chunk>4)
    throw Error("E_LIMIT");
}
std::uint64_t Scheduler::submit(const std::string &owner,const std::string &id,
                               std::vector<std::uint32_t> tokens,std::size_t limit) {
  if (!valid_id(owner) || !valid_id(id)) throw Error("E_FORMAT");
  const auto max=model_.cfg.positions;
  if (tokens.empty() || tokens.size()>max || limit==0 || limit>max-tokens.size())
    throw Error("E_LIMIT");
  for (auto t:tokens) if (t>=model_.cfg.vocab) throw Error("E_TOKEN");
  const Key key{owner,id};
  if (requests_.contains(key)) throw Error("E_DUPLICATE");
  const auto reserve=(tokens.size()+limit+page_tokens_-1)/page_tokens_;
  if (requests_.size()>=live_limit_ || reserve>arena_.capacity()-reserved_)
    throw Error("E_CAPACITY");
  if (next_==std::numeric_limits<std::uint64_t>::max()) throw Error("E_LIMIT");
  Owner handle{session_,owner,id,next_+1};
  Request r;
  r.owner=handle; r.prompt=std::move(tokens);r.limit=limit;r.reservation=reserve;
  r.cache=std::make_unique<PagedCache>(arena_,handle,model_.cfg,page_tokens_);
  requests_.emplace(key,std::move(r));
  // Publish reservation/generation only after all fallible admission allocations.
  reserved_+=reserve; ++next_;
  return next_;
}
void Scheduler::erase(std::map<Key,Request>::iterator it) {
  if (it->second.reservation>reserved_) throw Error("E_INTERNAL");
  reserved_-=it->second.reservation;
  requests_.erase(it); // cache RAII returns owned pages exactly once
}
Event Scheduler::cancel(const std::string &owner,const std::string &id,std::uint64_t generation) {
  const auto it=requests_.find({owner,id});
  if (it==requests_.end()) throw Error("E_NOT_FOUND");
  if (it->second.owner.generation!=generation) throw Error("E_STALE");
  Event event{"cancelled",owner,id,"",generation,0,0};
  erase(it);
  return event;
}
std::vector<Event> Scheduler::step() {
  std::vector<Event> events;
  // Bounded response storage is allocated before any state transition.
  events.reserve(requests_.size()*2);
  for (auto it=requests_.begin();it!=requests_.end();) {
    auto current=it++;
    auto &r=current->second;
    try {
      if (r.cursor<r.prompt.size()) {
        const auto stop=std::min(r.prompt.size(),r.cursor+chunk_);
        while (r.cursor<stop) {
          r.logits=forward(model_,*r.cache,r.prompt[r.cursor],r.cursor);
          ++r.cursor;
        }
        events.push_back({"prefill",r.owner.subject,r.owner.request,"",r.owner.generation,0,r.cursor});
      } else {
        const auto token=greedy(r.logits);
        // Perform next-state numeric work before committing an output token.
        // Final token needs no next-state forward pass.
        if (r.generated+1<r.limit)
          r.logits=forward(model_,*r.cache,token,r.prompt.size()+r.generated);
        ++r.generated;
        events.push_back({"token",r.owner.subject,r.owner.request,"",r.owner.generation,token,r.generated});
        if (r.generated==r.limit) {
          events.push_back({"finished",r.owner.subject,r.owner.request,"",r.owner.generation,0,r.generated});
          erase(current);
        }
      }
    } catch (const Error &e) {
      events.push_back({"failed",r.owner.subject,r.owner.request,e.what(),r.owner.generation,0,r.generated});
      erase(current);
    }
  }
  return events;
}
} // namespace bq
