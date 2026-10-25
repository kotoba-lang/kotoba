goog.provide('yotei.state');
if((typeof yotei !== 'undefined') && (typeof yotei.state !== 'undefined') && (typeof yotei.state.app !== 'undefined')){
} else {
yotei.state.app = reagent.core.atom.cljs$core$IFn$_invoke$arity$1(cljs.core.PersistentHashMap.fromArrays([new cljs.core.Keyword(null,"availability","availability",-1399524862),new cljs.core.Keyword(null,"bookings","bookings",-2001003516),new cljs.core.Keyword(null,"requester-did","requester-did",-880470684),new cljs.core.Keyword(null,"events","events",1792552201),new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326),new cljs.core.Keyword(null,"route","route",329891309),new cljs.core.Keyword(null,"loading","loading",-737050189),new cljs.core.Keyword(null,"result","result",1415092211),new cljs.core.Keyword(null,"submitting","submitting",472950900),new cljs.core.Keyword(null,"error","error",-978969032),new cljs.core.Keyword(null,"week-offset","week-offset",1808303834),new cljs.core.Keyword(null,"duration-min","duration-min",395781915),new cljs.core.Keyword(null,"message","message",-406056002)],[cljs.core.PersistentVector.EMPTY,cljs.core.PersistentVector.EMPTY,"",cljs.core.PersistentVector.EMPTY,"",new cljs.core.Keyword(null,"calendar","calendar",62308146),false,"",false,null,(0),(30),""]));
}
yotei.state.set_val = (function yotei$state$set_val(k,v){
return cljs.core.swap_BANG_.cljs$core$IFn$_invoke$arity$4(yotei.state.app,cljs.core.assoc,k,v);
});
yotei.state.json__GT_clj = (function yotei$state$json__GT_clj(j){
var parsed = cljs.core.js__GT_clj.cljs$core$IFn$_invoke$arity$variadic(j,cljs.core.prim_seq.cljs$core$IFn$_invoke$arity$2([new cljs.core.Keyword(null,"keywordize-keys","keywordize-keys",1310784252),true], 0));
return parsed;
});
yotei.state.xrpc = (function yotei$state$xrpc(nsid,params,on_ok){
var opts = ({"method": "POST", "headers": ({"Content-Type": "application/json"}), "body": JSON.stringify(cljs.core.clj__GT_js(params))});
return fetch(["/xrpc/",cljs.core.str.cljs$core$IFn$_invoke$arity$1(nsid)].join(''),opts).then((function (resp){
return resp.json();
})).then((function (json_body){
var G__22417 = yotei.state.json__GT_clj(json_body);
return (on_ok.cljs$core$IFn$_invoke$arity$1 ? on_ok.cljs$core$IFn$_invoke$arity$1(G__22417) : on_ok.call(null, G__22417));
})).catch((function (err){
return yotei.state.set_val(new cljs.core.Keyword(null,"error","error",-978969032),err.message);
}));
});

//# sourceMappingURL=yotei.state.js.map
