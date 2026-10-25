goog.provide('reagent.debug');
reagent.debug.has_console = (typeof console !== 'undefined');
reagent.debug.tracking = false;
if((typeof reagent !== 'undefined') && (typeof reagent.debug !== 'undefined') && (typeof reagent.debug.warnings !== 'undefined')){
} else {
reagent.debug.warnings = cljs.core.atom.cljs$core$IFn$_invoke$arity$1(null);
}
if((typeof reagent !== 'undefined') && (typeof reagent.debug !== 'undefined') && (typeof reagent.debug.track_console !== 'undefined')){
} else {
reagent.debug.track_console = (function (){var o = ({});
(o.warn = (function() { 
var G__21535__delegate = function (args){
return cljs.core.swap_BANG_.cljs$core$IFn$_invoke$arity$variadic(reagent.debug.warnings,cljs.core.update_in,new cljs.core.PersistentVector(null, 1, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"warn","warn",-436710552)], null),cljs.core.conj,cljs.core.prim_seq.cljs$core$IFn$_invoke$arity$2([cljs.core.apply.cljs$core$IFn$_invoke$arity$2(cljs.core.str,args)], 0));
};
var G__21535 = function (var_args){
var args = null;
if (arguments.length > 0) {
var G__21537__i = 0, G__21537__a = new Array(arguments.length -  0);
while (G__21537__i < G__21537__a.length) {G__21537__a[G__21537__i] = arguments[G__21537__i + 0]; ++G__21537__i;}
  args = new cljs.core.IndexedSeq(G__21537__a,0,null);
} 
return G__21535__delegate.call(this,args);};
G__21535.cljs$lang$maxFixedArity = 0;
G__21535.cljs$lang$applyTo = (function (arglist__21538){
var args = cljs.core.seq(arglist__21538);
return G__21535__delegate(args);
});
G__21535.cljs$core$IFn$_invoke$arity$variadic = G__21535__delegate;
return G__21535;
})()
);

(o.error = (function() { 
var G__21544__delegate = function (args){
return cljs.core.swap_BANG_.cljs$core$IFn$_invoke$arity$variadic(reagent.debug.warnings,cljs.core.update_in,new cljs.core.PersistentVector(null, 1, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"error","error",-978969032)], null),cljs.core.conj,cljs.core.prim_seq.cljs$core$IFn$_invoke$arity$2([cljs.core.apply.cljs$core$IFn$_invoke$arity$2(cljs.core.str,args)], 0));
};
var G__21544 = function (var_args){
var args = null;
if (arguments.length > 0) {
var G__21545__i = 0, G__21545__a = new Array(arguments.length -  0);
while (G__21545__i < G__21545__a.length) {G__21545__a[G__21545__i] = arguments[G__21545__i + 0]; ++G__21545__i;}
  args = new cljs.core.IndexedSeq(G__21545__a,0,null);
} 
return G__21544__delegate.call(this,args);};
G__21544.cljs$lang$maxFixedArity = 0;
G__21544.cljs$lang$applyTo = (function (arglist__21546){
var args = cljs.core.seq(arglist__21546);
return G__21544__delegate(args);
});
G__21544.cljs$core$IFn$_invoke$arity$variadic = G__21544__delegate;
return G__21544;
})()
);

return o;
})();
}
reagent.debug.track_warnings = (function reagent$debug$track_warnings(f){
(reagent.debug.tracking = true);

cljs.core.reset_BANG_(reagent.debug.warnings,null);

(f.cljs$core$IFn$_invoke$arity$0 ? f.cljs$core$IFn$_invoke$arity$0() : f.call(null, ));

var warns = cljs.core.deref(reagent.debug.warnings);
cljs.core.reset_BANG_(reagent.debug.warnings,null);

(reagent.debug.tracking = false);

return warns;
});

//# sourceMappingURL=reagent.debug.js.map
