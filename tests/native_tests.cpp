#include "scheduler.hpp"
#include <cmath>
#include <functional>
#include <iostream>
#include <limits>

namespace {
void require(bool condition,const char *message) {
  if(!condition) throw std::runtime_error(message);
}
template<class F> void rejects(const char *code,F fn) {
  try {fn();} catch(const bq::Error &e) {require(e.what()==std::string(code),"wrong error code");return;}
  throw std::runtime_error("operation unexpectedly accepted");
}
bq::Model fixture() {
  bq::Model m;
  m.cfg={11,8,16,2,2,1,64,1e-5F,10000.0F};
  m.embedding.assign(88,0.1F);m.norm.assign(8,1.0F);
  for(int i=0;i<2;++i) {
    bq::Layer l;
    l.norm1.assign(8,1);l.norm2.assign(8,1);
    l.q.assign(64,0.01F);l.k.assign(32,0.01F);l.v.assign(32,0.01F);l.o.assign(64,0.01F);
    l.gate.assign(128,0.01F);l.up.assign(128,0.01F);l.down.assign(128,0.01F);
    m.layers.push_back(l);
  }
  return m;
}
} // namespace
int main() {
  int passed=0;
  const auto test=[&](const char *name,const std::function<void()> &fn) {
    fn();++passed;std::cout<<"PASS "<<name<<'\n';
  };
  try {
    test("owner_rejection",[] {
      bq::Arena a(1,4);bq::Owner x{"s","a","r",1},y{"s","b","r",1};auto h=a.allocate(x);
      std::vector<float> values(4);
      rejects("E_OWNER",[&]{a.load(h,y,0,values);});
      rejects("E_OWNER",[&]{a.store(h,y,0,values);});
      rejects("E_OWNER",[&]{a.release(h,y);});require(a.used()==1,"owner rejection mutated arena");
    });
    test("reuse_zero_and_stale",[] {
      bq::Arena a(1,4);bq::Owner x{"s","a","r",1},y{"s","b","r",2};auto old=a.allocate(x);
      std::vector<float> written{0,0,17,0},retained(4);
      a.store(old,x,0,written);a.load(old,x,0,retained);a.release(old,x);auto h=a.allocate(y);
      std::vector<float> fresh(4);a.load(h,y,0,fresh);
      for(float v:fresh) require(v==0,"old bytes visible");
      retained[0]=29;a.load(h,y,0,fresh);
      for(float v:fresh) require(v==0,"retained copy aliases reassigned page");
      rejects("E_STALE",[&]{a.load(old,x,0,retained);});
      rejects("E_STALE",[&]{a.store(old,x,0,written);});
      rejects("E_STALE",[&]{a.release(old,x);});require(a.used()==1,"stale release changed counter");
      a.release(h,y);require(a.used()==0,"release leak");
    });
    test("same_id_new_generation",[] {
      bq::Arena a(1,4);bq::Owner x{"s","a","r",1},y{"s","a","r",2};auto h=a.allocate(x);
      std::vector<float> out(4);rejects("E_OWNER",[&]{a.load(h,y,0,out);});
    });
    test("arena_bounds",[] {
      rejects("E_LIMIT",[]{bq::Arena a(0,4);});rejects("E_LIMIT",[]{bq::Arena a(4096,1000000);});
      bq::Arena a(1,4);bq::Owner o{"s","a","r",1};auto h=a.allocate(o);
      rejects("E_CAPACITY",[&]{(void)a.allocate(o);});
      std::vector<float> out(4);rejects("E_STALE",[&]{a.load({99,1},o,0,out);});a.release(h,o);
      rejects("E_STALE",[&]{a.release(h,o);});
    });
    test("uninitialized_cache_rejected",[] {
      auto m=fixture();bq::Arena a(2,bq::page_elements(m.cfg,4));
      bq::PagedCache c(a,{"s","a","r",1},m.cfg,4);
      std::vector<float> out(4);rejects("E_STALE",[&]{c.copy_key(0,0,out);});
      std::vector<float> z(4,1);rejects("E_INTERNAL",[&]{c.put(0,1,z,z);});
      c.put(0,0,z,z);c.copy_key(0,0,out);require(out[0]==1,"cache write lost");
      rejects("E_STALE",[&]{c.copy_key(1,0,out);});
    });
    test("paged_contiguous_match",[] {
      auto m=fixture();bq::ContiguousCache c(m.cfg);bq::Arena a(8,bq::page_elements(m.cfg,4));
      {
        bq::PagedCache p(a,{"s","a","r",1},m.cfg,4);
        for(std::size_t i=0;i<31;++i) {
          const auto x=bq::forward(m,c,static_cast<std::uint32_t>(i%11),i);
          const auto y=bq::forward(m,p,static_cast<std::uint32_t>(i%11),i);
          require(x==y,"cache changed logits");
        }
        require(a.used()==8,"page boundary allocation wrong");
      }
      require(a.used()==0,"cache destructor leaked");
    });
    test("admission_atomic",[] {
      auto m=fixture();bq::Scheduler s(m,"s",2,4,16,4);const auto g=s.submit("a","r",{1,2},6);
      require(s.reserved()==2,"wrong reservation");
      rejects("E_CAPACITY",[&]{(void)s.submit("b","r",{1},1);});
      require(s.live()==1 && s.reserved()==2,"rejected admission changed state");
      (void)s.cancel("a","r",g);require(s.reserved()==0 && s.physical()==0,"cancel leak");
    });
    test("cancel_terminal",[] {
      auto m=fixture();bq::Scheduler s(m,"s",16,4,16,4);const auto g=s.submit("a","r",{1,2},4);
      (void)s.step();require(s.physical()>0,"test did not allocate");
      rejects("E_STALE",[&]{(void)s.cancel("a","r",g+1);});
      rejects("E_NOT_FOUND",[&]{(void)s.cancel("b","r",g);});
      (void)s.cancel("a","r",g);
      for(int i=0;i<5;++i) require(s.step().empty(),"cancelled request emitted output");
      require(s.physical()==0 && s.reserved()==0,"cancel resources leaked");
      const auto new_g=s.submit("a","r",{1},2);require(new_g>g,"generation reused");
      rejects("E_STALE",[&]{(void)s.cancel("a","r",g);});
    });
    test("chunk_bound",[] {
      auto m=fixture();bq::Scheduler s(m,"s",16,4,16,4);
      (void)s.submit("a","r",{1,2,3,4,5,6,7,8,9},2);
      auto x=s.step();require(x.size()==1 && x[0].event=="prefill" && x[0].index==4,"unbounded prefill");
      x=s.step();require(x[0].index==8,"chunk count wrong");
    });
    test("decode_grants_fair",[] {
      auto m=fixture();bq::Scheduler s(m,"s",32,4,16,4);
      (void)s.submit("a","r",{1},12);(void)s.submit("b","r",{2},12);(void)s.step();
      std::map<std::string,int> grants;
      for(int i=0;i<12;++i) {
        for(const auto &e:s.step()) if(e.event=="token") ++grants[e.owner];
        require(std::abs(grants["a"]-grants["b"])<=1,"unfair grants");
      }
      require(grants["a"]==12 && grants["b"]==12,"missing grants");
      require(s.live()==0 && s.reserved()==0 && s.physical()==0,"completion leak");
    });
    test("arrival_order_not_lexical",[] {
      auto m=fixture();bq::Scheduler s(m,"s",32,4,16,4);
      (void)s.submit("z","r",{1},3);(void)s.submit("a","r",{2},3);
      auto events=s.step();
      require(events.size()==2 && events[0].owner=="z" && events[1].owner=="a",
              "scheduler ignored arrival order");
      (void)s.cancel("z","r",1);
      events=s.step();
      require(!events.empty() && events[0].owner=="a","cancelled request remained ready");
      (void)s.submit("m","r",{3},1);
      events=s.step();
      require(events.size()>=2 && events[0].owner=="a" && events[1].owner=="m",
              "new arrival displaced ready request");
    });
    test("forward_failure_reclaims",[] {
      auto m=fixture();m.layers[1].q.assign(64,std::numeric_limits<float>::max());
      bq::Arena arena(16,bq::page_elements(m.cfg,4));
      {
        bq::PagedCache cache(arena,{"s","partial","r",1},m.cfg,4);
        rejects("E_NUMERIC",[&]{(void)bq::forward(m,cache,1,0);});
        require(arena.used()>0,"failure happened before any physical allocation");
      }
      require(arena.used()==0,"partial forward cache destructor leaked pages");
      bq::Scheduler s(m,"s",16,4,16,4);(void)s.submit("a","r",{1},4);
      const auto events=s.step();require(events.size()==1 && events[0].event=="failed","failure not explicit");
      require(events[0].code=="E_NUMERIC","wrong forward failure");
      require(s.live()==0 && s.reserved()==0 && s.physical()==0,"failure leaked capacity");
    });
    test("transient_resource_peaks",[] {
      auto m=fixture();bq::Scheduler s(m,"s",4,4,2,4);
      (void)s.submit("a","r",{1,2,3,4},3);(void)s.submit("b","r",{4,3,2,1},1);
      (void)s.step();(void)s.step();
      require(s.physical()==2,"expected post-round page count");
      require(s.peak_physical()==3,"transient allocation peak missed");
      require(s.peak_cached_tokens()==9,"transient complete-token KV peak missed");
      require(s.allocated_payload_bytes()>=3*bq::page_elements(m.cfg,4)*sizeof(float),"retained payload capacity missed");
      while(s.live()) (void)s.step();
      require(s.physical()==0 && s.reserved()==0 && s.peak_physical()==3,"peak lost during reclamation");
    });
    test("shape_guard",[] {
      auto c=fixture().cfg;c.heads=0;rejects("E_MODEL",[&]{c.validate();});
      c=fixture().cfg;c.kv_heads=3;rejects("E_MODEL",[&]{c.validate();});
      c=fixture().cfg;c.theta=std::numeric_limits<float>::quiet_NaN();rejects("E_MODEL",[&]{c.validate();});
    });
    test("greedy_tie",[] {require(bq::greedy(std::vector<float>{1,2,2})==1,"tie handling changed");});
    test("invalid_ids",[] {require(!bq::valid_id("a\"b") && !bq::valid_id("") && bq::valid_id("a_B-2"),"ID grammar");});
    test("duplicate_and_token",[] {
      auto m=fixture();bq::Scheduler s(m,"s",16,4,16,4);(void)s.submit("a","r",{1},1);
      rejects("E_DUPLICATE",[&]{(void)s.submit("a","r",{1},1);});
      rejects("E_TOKEN",[&]{(void)s.submit("b","r",{11},1);});
      rejects("E_LIMIT",[&]{(void)s.submit("b","r",{},1);});
      require(s.live()==1,"invalid request admitted");
    });
    std::cout<<"NATIVE_TESTS="<<passed<<'\n';return 0;
  } catch(const std::exception &e) {std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}
}
