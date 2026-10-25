goog.provide('yotei.ui');
yotei.ui.fmt_date = (function yotei$ui$fmt_date(js_date){
return cljs.core.subs.cljs$core$IFn$_invoke$arity$3(js_date.toISOString(),(0),(10));
});
yotei.ui.new_date = (function yotei$ui$new_date(offset_days){
var d = (new Date());
d.setHours((0),(0),(0));

d.setDate((d.getDate() + offset_days));

return d;
});
yotei.ui.week_start = (function yotei$ui$week_start(){
var d = (new Date());
var dow = d.getDay();
var off = (((1) - dow) + ((7) * new cljs.core.Keyword(null,"week-offset","week-offset",1808303834).cljs$core$IFn$_invoke$arity$1(cljs.core.deref(yotei.state.app))));
d.setHours((0),(0),(0));

d.setDate((d.getDate() + off));

return d;
});
yotei.ui.pad2 = (function yotei$ui$pad2(n){
if((n < (10))){
return ["0",cljs.core.str.cljs$core$IFn$_invoke$arity$1(n)].join('');
} else {
return cljs.core.str.cljs$core$IFn$_invoke$arity$1(n);
}
});
yotei.ui.hour_hhmm = (function yotei$ui$hour_hhmm(hour){
return [yotei.ui.pad2(hour),":00"].join('');
});
yotei.ui.dow_available_QMARK_ = (function yotei$ui$dow_available_QMARK_(availability,dow,hour){
var hhmm = yotei.ui.hour_hhmm(hour);
return cljs.core.boolean$(cljs.core.some((function (a){
return ((cljs.core._EQ_.cljs$core$IFn$_invoke$arity$2(new cljs.core.Keyword(null,"day-of-week","day-of-week",1639326729).cljs$core$IFn$_invoke$arity$1(a),dow)) && ((((!((cljs.core.compare(new cljs.core.Keyword(null,"start-time","start-time",814801386).cljs$core$IFn$_invoke$arity$1(a),hhmm) > (0))))) && ((cljs.core.compare(new cljs.core.Keyword(null,"end-time","end-time",-1849817460).cljs$core$IFn$_invoke$arity$1(a),hhmm) > (0))))));
}),availability));
});
yotei.ui.events_at = (function yotei$ui$events_at(events,date_str,hour){
return cljs.core.filter.cljs$core$IFn$_invoke$arity$2((function (e){
var s = cljs.core.str.cljs$core$IFn$_invoke$arity$1(new cljs.core.Keyword(null,"start-at","start-at",-103334680).cljs$core$IFn$_invoke$arity$1(e));
var e_date = cljs.core.subs.cljs$core$IFn$_invoke$arity$3(s,(0),(10));
var e_hour = parseInt(cljs.core.subs.cljs$core$IFn$_invoke$arity$3(s,(11),(13)),(10));
return ((cljs.core._EQ_.cljs$core$IFn$_invoke$arity$2(e_date,date_str)) && (cljs.core._EQ_.cljs$core$IFn$_invoke$arity$2(e_hour,hour)));
}),events);
});
yotei.ui.load_week = (function yotei$ui$load_week(){
var cal_id = new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326).cljs$core$IFn$_invoke$arity$1(cljs.core.deref(yotei.state.app));
if(cljs.core.seq(cal_id)){
yotei.state.set_val(new cljs.core.Keyword(null,"loading","loading",-737050189),true);

var start = yotei.ui.week_start();
var end_d = (new Date(start.getTime()));
var _ = end_d.setDate((end_d.getDate() + (6)));
var start_str = yotei.ui.fmt_date(start);
var end_str = yotei.ui.fmt_date(end_d);
return yotei.state.xrpc("com.etzhayyim.apps.yotei.getAvailability",new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"calendarId","calendarId",-615509947),cal_id], null),(function (avail_res){
yotei.state.set_val(new cljs.core.Keyword(null,"availability","availability",-1399524862),cljs.core.get.cljs$core$IFn$_invoke$arity$3(avail_res,new cljs.core.Keyword(null,"availability","availability",-1399524862),cljs.core.PersistentVector.EMPTY));

return yotei.state.xrpc("com.etzhayyim.apps.yotei.listEvents",new cljs.core.PersistentArrayMap(null, 3, [new cljs.core.Keyword(null,"calendarId","calendarId",-615509947),cal_id,new cljs.core.Keyword(null,"dateFrom","dateFrom",-1351798484),start_str,new cljs.core.Keyword(null,"dateTo","dateTo",290078800),end_str], null),(function (evt_res){
yotei.state.set_val(new cljs.core.Keyword(null,"events","events",1792552201),cljs.core.get.cljs$core$IFn$_invoke$arity$3(evt_res,new cljs.core.Keyword(null,"events","events",1792552201),cljs.core.PersistentVector.EMPTY));

return yotei.state.set_val(new cljs.core.Keyword(null,"loading","loading",-737050189),false);
}));
}));
} else {
return null;
}
});
yotei.ui.input_value = (function yotei$ui$input_value(e){
return e.target.value;
});
yotei.ui.dow_cell = (function yotei$ui$dow_cell(availability,events,ws,hour,dow){
var d = (new Date(ws.getTime()));
d.setDate((d.getDate() + dow));

var date_str = yotei.ui.fmt_date(d);
var real_dow = cljs.core.mod((dow + (1)),(7));
var avail_QMARK_ = yotei.ui.dow_available_QMARK_(availability,real_dow,hour);
var hour_events = yotei.ui.events_at(events,date_str,hour);
return cljs.core.with_meta(new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"td","td",1479933353),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),["yt-cell",((avail_QMARK_)?" yt-cell-avail":null)].join('')], null),cljs.core.doall.cljs$core$IFn$_invoke$arity$1((function (){var iter__5480__auto__ = (function yotei$ui$dow_cell_$_iter__20108(s__20109){
return (new cljs.core.LazySeq(null,(function (){
var s__20109__$1 = s__20109;
while(true){
var temp__5823__auto__ = cljs.core.seq(s__20109__$1);
if(temp__5823__auto__){
var s__20109__$2 = temp__5823__auto__;
if(cljs.core.chunked_seq_QMARK_(s__20109__$2)){
var c__5478__auto__ = cljs.core.chunk_first(s__20109__$2);
var size__5479__auto__ = cljs.core.count(c__5478__auto__);
var b__20111 = cljs.core.chunk_buffer(size__5479__auto__);
if((function (){var i__20110 = (0);
while(true){
if((i__20110 < size__5479__auto__)){
var evt = cljs.core._nth(c__5478__auto__,i__20110);
cljs.core.chunk_append(b__20111,cljs.core.with_meta(new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-evt"], null),new cljs.core.Keyword(null,"title","title",636505583).cljs$core$IFn$_invoke$arity$1(evt)], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(evt)], null)));

var G__20148 = (i__20110 + (1));
i__20110 = G__20148;
continue;
} else {
return true;
}
break;
}
})()){
return cljs.core.chunk_cons(cljs.core.chunk(b__20111),yotei$ui$dow_cell_$_iter__20108(cljs.core.chunk_rest(s__20109__$2)));
} else {
return cljs.core.chunk_cons(cljs.core.chunk(b__20111),null);
}
} else {
var evt = cljs.core.first(s__20109__$2);
return cljs.core.cons(cljs.core.with_meta(new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-evt"], null),new cljs.core.Keyword(null,"title","title",636505583).cljs$core$IFn$_invoke$arity$1(evt)], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(evt)], null)),yotei$ui$dow_cell_$_iter__20108(cljs.core.rest(s__20109__$2)));
}
} else {
return null;
}
break;
}
}),null,null));
});
return iter__5480__auto__(hour_events);
})())], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),dow], null));
});
yotei.ui.hour_row = (function yotei$ui$hour_row(availability,events,ws,hour){
var cells = cljs.core.doall.cljs$core$IFn$_invoke$arity$1((function (){var iter__5480__auto__ = (function yotei$ui$hour_row_$_iter__20112(s__20113){
return (new cljs.core.LazySeq(null,(function (){
var s__20113__$1 = s__20113;
while(true){
var temp__5823__auto__ = cljs.core.seq(s__20113__$1);
if(temp__5823__auto__){
var s__20113__$2 = temp__5823__auto__;
if(cljs.core.chunked_seq_QMARK_(s__20113__$2)){
var c__5478__auto__ = cljs.core.chunk_first(s__20113__$2);
var size__5479__auto__ = cljs.core.count(c__5478__auto__);
var b__20115 = cljs.core.chunk_buffer(size__5479__auto__);
if((function (){var i__20114 = (0);
while(true){
if((i__20114 < size__5479__auto__)){
var dow = cljs.core._nth(c__5478__auto__,i__20114);
cljs.core.chunk_append(b__20115,yotei.ui.dow_cell(availability,events,ws,hour,dow));

var G__20149 = (i__20114 + (1));
i__20114 = G__20149;
continue;
} else {
return true;
}
break;
}
})()){
return cljs.core.chunk_cons(cljs.core.chunk(b__20115),yotei$ui$hour_row_$_iter__20112(cljs.core.chunk_rest(s__20113__$2)));
} else {
return cljs.core.chunk_cons(cljs.core.chunk(b__20115),null);
}
} else {
var dow = cljs.core.first(s__20113__$2);
return cljs.core.cons(yotei.ui.dow_cell(availability,events,ws,hour,dow),yotei$ui$hour_row_$_iter__20112(cljs.core.rest(s__20113__$2)));
}
} else {
return null;
}
break;
}
}),null,null));
});
return iter__5480__auto__(cljs.core.range.cljs$core$IFn$_invoke$arity$1((7)));
})());
return cljs.core.with_meta(new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"tr","tr",-1424774646),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"td","td",1479933353),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"hour-label"], null),[cljs.core.str.cljs$core$IFn$_invoke$arity$1(hour),":00"].join('')], null),cells], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),hour], null));
});
yotei.ui.calendar_view = (function yotei$ui$calendar_view(){
var map__20116 = cljs.core.deref(yotei.state.app);
var map__20116__$1 = cljs.core.__destructure_map(map__20116);
var calendar_id = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20116__$1,new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326));
var availability = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20116__$1,new cljs.core.Keyword(null,"availability","availability",-1399524862));
var events = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20116__$1,new cljs.core.Keyword(null,"events","events",1792552201));
var loading = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20116__$1,new cljs.core.Keyword(null,"loading","loading",-737050189));
var week_offset = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20116__$1,new cljs.core.Keyword(null,"week-offset","week-offset",1808303834));
var day_names = new cljs.core.PersistentVector(null, 7, 5, cljs.core.PersistentVector.EMPTY_NODE, ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"], null);
var hours = cljs.core.vec(cljs.core.range.cljs$core$IFn$_invoke$arity$2((7),(21)));
var ws = yotei.ui.week_start();
var header_dow = (function (dow){
var d = (new Date(ws.getTime()));
d.setDate((d.getDate() + dow));

return cljs.core.with_meta(new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"th","th",-545608566),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"dow"], null),(function (){var G__20117 = cljs.core.mod((dow + (1)),(7));
return (day_names.cljs$core$IFn$_invoke$arity$1 ? day_names.cljs$core$IFn$_invoke$arity$1(G__20117) : day_names.call(null, G__20117));
})()], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"dom"], null),d.getDate()], null)], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),dow], null));
});
var rows = cljs.core.doall.cljs$core$IFn$_invoke$arity$1((function (){var iter__5480__auto__ = (function yotei$ui$calendar_view_$_iter__20118(s__20119){
return (new cljs.core.LazySeq(null,(function (){
var s__20119__$1 = s__20119;
while(true){
var temp__5823__auto__ = cljs.core.seq(s__20119__$1);
if(temp__5823__auto__){
var s__20119__$2 = temp__5823__auto__;
if(cljs.core.chunked_seq_QMARK_(s__20119__$2)){
var c__5478__auto__ = cljs.core.chunk_first(s__20119__$2);
var size__5479__auto__ = cljs.core.count(c__5478__auto__);
var b__20121 = cljs.core.chunk_buffer(size__5479__auto__);
if((function (){var i__20120 = (0);
while(true){
if((i__20120 < size__5479__auto__)){
var hour = cljs.core._nth(c__5478__auto__,i__20120);
cljs.core.chunk_append(b__20121,yotei.ui.hour_row(availability,events,ws,hour));

var G__20150 = (i__20120 + (1));
i__20120 = G__20150;
continue;
} else {
return true;
}
break;
}
})()){
return cljs.core.chunk_cons(cljs.core.chunk(b__20121),yotei$ui$calendar_view_$_iter__20118(cljs.core.chunk_rest(s__20119__$2)));
} else {
return cljs.core.chunk_cons(cljs.core.chunk(b__20121),null);
}
} else {
var hour = cljs.core.first(s__20119__$2);
return cljs.core.cons(yotei.ui.hour_row(availability,events,ws,hour),yotei$ui$calendar_view_$_iter__20118(cljs.core.rest(s__20119__$2)));
}
} else {
return null;
}
break;
}
}),null,null));
});
return iter__5480__auto__(hours);
})());
return new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-row"], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"input","input",556931961),new cljs.core.PersistentArrayMap(null, 5, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-input",new cljs.core.Keyword(null,"type","type",1174270348),"text",new cljs.core.Keyword(null,"placeholder","placeholder",-104873083),"Calendar ID",new cljs.core.Keyword(null,"value","value",305978217),calendar_id,new cljs.core.Keyword(null,"on-change","on-change",-732046149),(function (e){
return yotei.state.set_val(new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326),yotei.ui.input_value(e));
})], null)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-btn",new cljs.core.Keyword(null,"on-click","on-click",1632826543),yotei.ui.load_week], null),"Load"], null)], null),new cljs.core.PersistentVector(null, 5, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-spread"], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-btn-ghost",new cljs.core.Keyword(null,"on-click","on-click",1632826543),(function (_){
yotei.state.set_val(new cljs.core.Keyword(null,"week-offset","week-offset",1808303834),(week_offset - (1)));

return yotei.ui.load_week();
})], null),"Prev"], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),[yotei.ui.fmt_date(ws)," week"].join('')], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-btn-ghost",new cljs.core.Keyword(null,"on-click","on-click",1632826543),(function (_){
yotei.state.set_val(new cljs.core.Keyword(null,"week-offset","week-offset",1808303834),(week_offset + (1)));

return yotei.ui.load_week();
})], null),"Next"], null)], null),(cljs.core.truth_(loading)?new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-center"], null),"Loading..."], null):new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-calendar-scroll"], null),new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"table","table",-564943036),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-cal"], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"thead","thead",-291875296),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"tr","tr",-1424774646),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"th","th",-545608566),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"width","width",-384071477),"48px"], null)], null)], null),cljs.core.doall.cljs$core$IFn$_invoke$arity$1(cljs.core.map.cljs$core$IFn$_invoke$arity$2(header_dow,cljs.core.range.cljs$core$IFn$_invoke$arity$1((7))))], null)], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"tbody","tbody",-80678300),rows], null)], null)], null))], null);
});
yotei.ui.status_badge = (function yotei$ui$status_badge(status){
return new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),["yt-badge yt-badge-",cljs.core.name((function (){var or__5002__auto__ = status;
if(cljs.core.truth_(or__5002__auto__)){
return or__5002__auto__;
} else {
return new cljs.core.Keyword(null,"proposed","proposed",-1319961107);
}
})())].join('')], null),cljs.core.name((function (){var or__5002__auto__ = status;
if(cljs.core.truth_(or__5002__auto__)){
return or__5002__auto__;
} else {
return new cljs.core.Keyword(null,"proposed","proposed",-1319961107);
}
})())], null);
});
yotei.ui.load_bookings = (function yotei$ui$load_bookings(){
var cal_id = new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326).cljs$core$IFn$_invoke$arity$1(cljs.core.deref(yotei.state.app));
if(cljs.core.seq(cal_id)){
return yotei.state.xrpc("com.etzhayyim.apps.yotei.listBookings",new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"calendarId","calendarId",-615509947),cal_id], null),(function (res){
return yotei.state.set_val(new cljs.core.Keyword(null,"bookings","bookings",-2001003516),cljs.core.get.cljs$core$IFn$_invoke$arity$3(res,new cljs.core.Keyword(null,"bookings","bookings",-2001003516),cljs.core.PersistentVector.EMPTY));
}));
} else {
return null;
}
});
yotei.ui.propose_booking = (function yotei$ui$propose_booking(){
var map__20122 = cljs.core.deref(yotei.state.app);
var map__20122__$1 = cljs.core.__destructure_map(map__20122);
var calendar_id = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20122__$1,new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326));
var requester_did = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20122__$1,new cljs.core.Keyword(null,"requester-did","requester-did",-880470684));
var duration_min = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20122__$1,new cljs.core.Keyword(null,"duration-min","duration-min",395781915));
var message = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20122__$1,new cljs.core.Keyword(null,"message","message",-406056002));
if(((cljs.core.seq(calendar_id)) && (cljs.core.seq(requester_did)))){
yotei.state.set_val(new cljs.core.Keyword(null,"submitting","submitting",472950900),true);

yotei.state.set_val(new cljs.core.Keyword(null,"result","result",1415092211),"");

return yotei.state.xrpc("com.etzhayyim.apps.yotei.proposeBooking",new cljs.core.PersistentArrayMap(null, 4, [new cljs.core.Keyword(null,"calendarId","calendarId",-615509947),calendar_id,new cljs.core.Keyword(null,"requesterDid","requesterDid",-6798514),requester_did,new cljs.core.Keyword(null,"durationMin","durationMin",-593499615),duration_min,new cljs.core.Keyword(null,"message","message",-406056002),message], null),(function (res){
yotei.state.set_val(new cljs.core.Keyword(null,"result","result",1415092211),["Booking ",cljs.core.str.cljs$core$IFn$_invoke$arity$1(new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(res))," \u2014 ",cljs.core.str.cljs$core$IFn$_invoke$arity$1(new cljs.core.Keyword(null,"status","status",-1997798413).cljs$core$IFn$_invoke$arity$1(res))].join(''));

yotei.state.set_val(new cljs.core.Keyword(null,"submitting","submitting",472950900),false);

return yotei.ui.load_bookings();
}));
} else {
return null;
}
});
yotei.ui.booking_view = (function yotei$ui$booking_view(){
var map__20123 = cljs.core.deref(yotei.state.app);
var map__20123__$1 = cljs.core.__destructure_map(map__20123);
var calendar_id = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20123__$1,new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326));
var requester_did = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20123__$1,new cljs.core.Keyword(null,"requester-did","requester-did",-880470684));
var duration_min = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20123__$1,new cljs.core.Keyword(null,"duration-min","duration-min",395781915));
var message = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20123__$1,new cljs.core.Keyword(null,"message","message",-406056002));
var submitting = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20123__$1,new cljs.core.Keyword(null,"submitting","submitting",472950900));
var result = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20123__$1,new cljs.core.Keyword(null,"result","result",1415092211));
var bookings = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20123__$1,new cljs.core.Keyword(null,"bookings","bookings",-2001003516));
return new cljs.core.PersistentVector(null, 5, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"h2","h2",-372662728),"Book a Meeting"], null),new cljs.core.PersistentVector(null, 8, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-form"], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"input","input",556931961),new cljs.core.PersistentArrayMap(null, 5, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-input",new cljs.core.Keyword(null,"type","type",1174270348),"text",new cljs.core.Keyword(null,"placeholder","placeholder",-104873083),"Calendar ID",new cljs.core.Keyword(null,"value","value",305978217),calendar_id,new cljs.core.Keyword(null,"on-change","on-change",-732046149),(function (e){
return yotei.state.set_val(new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326),yotei.ui.input_value(e));
})], null)], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"input","input",556931961),new cljs.core.PersistentArrayMap(null, 5, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-input",new cljs.core.Keyword(null,"type","type",1174270348),"text",new cljs.core.Keyword(null,"placeholder","placeholder",-104873083),"Your DID (did:web:...)",new cljs.core.Keyword(null,"value","value",305978217),requester_did,new cljs.core.Keyword(null,"on-change","on-change",-732046149),(function (e){
return yotei.state.set_val(new cljs.core.Keyword(null,"requester-did","requester-did",-880470684),yotei.ui.input_value(e));
})], null)], null),new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-row"], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-muted"], null),"Duration"], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"select","select",1147833503),new cljs.core.PersistentArrayMap(null, 3, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-select",new cljs.core.Keyword(null,"value","value",305978217),duration_min,new cljs.core.Keyword(null,"on-change","on-change",-732046149),(function (e){
return yotei.state.set_val(new cljs.core.Keyword(null,"duration-min","duration-min",395781915),parseInt(yotei.ui.input_value(e),(10)));
})], null),cljs.core.doall.cljs$core$IFn$_invoke$arity$1((function (){var iter__5480__auto__ = (function yotei$ui$booking_view_$_iter__20124(s__20125){
return (new cljs.core.LazySeq(null,(function (){
var s__20125__$1 = s__20125;
while(true){
var temp__5823__auto__ = cljs.core.seq(s__20125__$1);
if(temp__5823__auto__){
var s__20125__$2 = temp__5823__auto__;
if(cljs.core.chunked_seq_QMARK_(s__20125__$2)){
var c__5478__auto__ = cljs.core.chunk_first(s__20125__$2);
var size__5479__auto__ = cljs.core.count(c__5478__auto__);
var b__20127 = cljs.core.chunk_buffer(size__5479__auto__);
if((function (){var i__20126 = (0);
while(true){
if((i__20126 < size__5479__auto__)){
var d = cljs.core._nth(c__5478__auto__,i__20126);
cljs.core.chunk_append(b__20127,cljs.core.with_meta(new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"option","option",65132272),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"value","value",305978217),d], null),[cljs.core.str.cljs$core$IFn$_invoke$arity$1(d)," min"].join('')], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),d], null)));

var G__20151 = (i__20126 + (1));
i__20126 = G__20151;
continue;
} else {
return true;
}
break;
}
})()){
return cljs.core.chunk_cons(cljs.core.chunk(b__20127),yotei$ui$booking_view_$_iter__20124(cljs.core.chunk_rest(s__20125__$2)));
} else {
return cljs.core.chunk_cons(cljs.core.chunk(b__20127),null);
}
} else {
var d = cljs.core.first(s__20125__$2);
return cljs.core.cons(cljs.core.with_meta(new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"option","option",65132272),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"value","value",305978217),d], null),[cljs.core.str.cljs$core$IFn$_invoke$arity$1(d)," min"].join('')], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),d], null)),yotei$ui$booking_view_$_iter__20124(cljs.core.rest(s__20125__$2)));
}
} else {
return null;
}
break;
}
}),null,null));
});
return iter__5480__auto__(new cljs.core.PersistentVector(null, 5, 5, cljs.core.PersistentVector.EMPTY_NODE, [(15),(30),(45),(60),(90)], null));
})())], null)], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"textarea","textarea",-650375824),new cljs.core.PersistentArrayMap(null, 5, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-textarea",new cljs.core.Keyword(null,"rows","rows",850049680),(2),new cljs.core.Keyword(null,"placeholder","placeholder",-104873083),"Message (optional)",new cljs.core.Keyword(null,"value","value",305978217),message,new cljs.core.Keyword(null,"on-change","on-change",-732046149),(function (e){
return yotei.state.set_val(new cljs.core.Keyword(null,"message","message",-406056002),yotei.ui.input_value(e));
})], null)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 3, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-btn",new cljs.core.Keyword(null,"disabled","disabled",-1529784218),(function (){var or__5002__auto__ = submitting;
if(cljs.core.truth_(or__5002__auto__)){
return or__5002__auto__;
} else {
return ((cljs.core.not(cljs.core.seq(calendar_id))) || (cljs.core.not(cljs.core.seq(requester_did))));
}
})(),new cljs.core.Keyword(null,"on-click","on-click",1632826543),yotei.ui.propose_booking], null),(cljs.core.truth_(submitting)?"Proposing...":"Propose Booking")], null),((cljs.core.seq(result))?new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-result"], null),result], null):null)], null),new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-spread"], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"h3","h3",2067611163),"Bookings"], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-link",new cljs.core.Keyword(null,"on-click","on-click",1632826543),yotei.ui.load_bookings], null),"Refresh"], null)], null),((cljs.core.empty_QMARK_(bookings))?new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-center"], null),"No bookings yet"], null):new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-stack"], null),cljs.core.doall.cljs$core$IFn$_invoke$arity$1((function (){var iter__5480__auto__ = (function yotei$ui$booking_view_$_iter__20128(s__20129){
return (new cljs.core.LazySeq(null,(function (){
var s__20129__$1 = s__20129;
while(true){
var temp__5823__auto__ = cljs.core.seq(s__20129__$1);
if(temp__5823__auto__){
var s__20129__$2 = temp__5823__auto__;
if(cljs.core.chunked_seq_QMARK_(s__20129__$2)){
var c__5478__auto__ = cljs.core.chunk_first(s__20129__$2);
var size__5479__auto__ = cljs.core.count(c__5478__auto__);
var b__20131 = cljs.core.chunk_buffer(size__5479__auto__);
if((function (){var i__20130 = (0);
while(true){
if((i__20130 < size__5479__auto__)){
var bk = cljs.core._nth(c__5478__auto__,i__20130);
cljs.core.chunk_append(b__20131,cljs.core.with_meta(new cljs.core.PersistentVector(null, 6, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-card"], null),new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-spread",new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"margin-bottom","margin-bottom",388334941),"4px"], null)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-mono"], null),new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(bk)], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [yotei.ui.status_badge,new cljs.core.Keyword(null,"status","status",-1997798413).cljs$core$IFn$_invoke$arity$1(bk)], null)], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.Keyword(null,"requester-did","requester-did",-880470684).cljs$core$IFn$_invoke$arity$1(bk)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-dim",new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"11px"], null)], null),[cljs.core.str.cljs$core$IFn$_invoke$arity$1(new cljs.core.Keyword(null,"duration-min","duration-min",395781915).cljs$core$IFn$_invoke$arity$1(bk)),"min \u2014 ",cljs.core.subs.cljs$core$IFn$_invoke$arity$3(cljs.core.str.cljs$core$IFn$_invoke$arity$1(new cljs.core.Keyword(null,"created-at","created-at",-89248644).cljs$core$IFn$_invoke$arity$1(bk)),(0),(16))].join('')], null),(function (){var temp__5823__auto____$1 = new cljs.core.Keyword(null,"confirmed-slot","confirmed-slot",1247685445).cljs$core$IFn$_invoke$arity$1(bk);
if(cljs.core.truth_(temp__5823__auto____$1)){
var slot = temp__5823__auto____$1;
return new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 3, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"11px",new cljs.core.Keyword(null,"color","color",1011675173),"#4ade80",new cljs.core.Keyword(null,"margin-top","margin-top",392161226),"4px"], null)], null),["Confirmed: ",cljs.core.str.cljs$core$IFn$_invoke$arity$1(slot)].join('')], null);
} else {
return null;
}
})()], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(bk)], null)));

var G__20152 = (i__20130 + (1));
i__20130 = G__20152;
continue;
} else {
return true;
}
break;
}
})()){
return cljs.core.chunk_cons(cljs.core.chunk(b__20131),yotei$ui$booking_view_$_iter__20128(cljs.core.chunk_rest(s__20129__$2)));
} else {
return cljs.core.chunk_cons(cljs.core.chunk(b__20131),null);
}
} else {
var bk = cljs.core.first(s__20129__$2);
return cljs.core.cons(cljs.core.with_meta(new cljs.core.PersistentVector(null, 6, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-card"], null),new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-spread",new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"margin-bottom","margin-bottom",388334941),"4px"], null)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-mono"], null),new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(bk)], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [yotei.ui.status_badge,new cljs.core.Keyword(null,"status","status",-1997798413).cljs$core$IFn$_invoke$arity$1(bk)], null)], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.Keyword(null,"requester-did","requester-did",-880470684).cljs$core$IFn$_invoke$arity$1(bk)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-dim",new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"11px"], null)], null),[cljs.core.str.cljs$core$IFn$_invoke$arity$1(new cljs.core.Keyword(null,"duration-min","duration-min",395781915).cljs$core$IFn$_invoke$arity$1(bk)),"min \u2014 ",cljs.core.subs.cljs$core$IFn$_invoke$arity$3(cljs.core.str.cljs$core$IFn$_invoke$arity$1(new cljs.core.Keyword(null,"created-at","created-at",-89248644).cljs$core$IFn$_invoke$arity$1(bk)),(0),(16))].join('')], null),(function (){var temp__5823__auto____$1 = new cljs.core.Keyword(null,"confirmed-slot","confirmed-slot",1247685445).cljs$core$IFn$_invoke$arity$1(bk);
if(cljs.core.truth_(temp__5823__auto____$1)){
var slot = temp__5823__auto____$1;
return new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 3, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"11px",new cljs.core.Keyword(null,"color","color",1011675173),"#4ade80",new cljs.core.Keyword(null,"margin-top","margin-top",392161226),"4px"], null)], null),["Confirmed: ",cljs.core.str.cljs$core$IFn$_invoke$arity$1(slot)].join('')], null);
} else {
return null;
}
})()], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(bk)], null)),yotei$ui$booking_view_$_iter__20128(cljs.core.rest(s__20129__$2)));
}
} else {
return null;
}
break;
}
}),null,null));
});
return iter__5480__auto__(bookings);
})())], null))], null);
});
yotei.ui.fmt_dt = (function yotei$ui$fmt_dt(iso){
var s = cljs.core.str.cljs$core$IFn$_invoke$arity$1(iso);
if(cljs.core.seq(s)){
var d = (new Date(s));
return [cljs.core.str.cljs$core$IFn$_invoke$arity$1(d.toLocaleDateString("ja-JP",({"month": "short", "day": "numeric", "weekday": "short"})))," ",cljs.core.str.cljs$core$IFn$_invoke$arity$1(d.toLocaleTimeString("ja-JP",({"hour": "2-digit", "minute": "2-digit"})))].join('');
} else {
return null;
}
});
yotei.ui.cancel_event = (function yotei$ui$cancel_event(id){
return yotei.state.xrpc("com.etzhayyim.apps.yotei.cancelEvent",new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"id","id",-1388402092),id], null),(function (_){
var cal_id = new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326).cljs$core$IFn$_invoke$arity$1(cljs.core.deref(yotei.state.app));
if(cljs.core.seq(cal_id)){
return yotei.state.xrpc("com.etzhayyim.apps.yotei.listEvents",new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"calendarId","calendarId",-615509947),cal_id,new cljs.core.Keyword(null,"dateFrom","dateFrom",-1351798484),(new Date()).toISOString()], null),(function (res){
return yotei.state.set_val(new cljs.core.Keyword(null,"events","events",1792552201),cljs.core.get.cljs$core$IFn$_invoke$arity$3(res,new cljs.core.Keyword(null,"events","events",1792552201),cljs.core.PersistentVector.EMPTY));
}));
} else {
return null;
}
}));
});
yotei.ui.load_events = (function yotei$ui$load_events(){
var cal_id = new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326).cljs$core$IFn$_invoke$arity$1(cljs.core.deref(yotei.state.app));
if(cljs.core.seq(cal_id)){
yotei.state.set_val(new cljs.core.Keyword(null,"loading","loading",-737050189),true);

return yotei.state.xrpc("com.etzhayyim.apps.yotei.listEvents",new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"calendarId","calendarId",-615509947),cal_id,new cljs.core.Keyword(null,"dateFrom","dateFrom",-1351798484),(new Date()).toISOString()], null),(function (res){
yotei.state.set_val(new cljs.core.Keyword(null,"events","events",1792552201),cljs.core.get.cljs$core$IFn$_invoke$arity$3(res,new cljs.core.Keyword(null,"events","events",1792552201),cljs.core.PersistentVector.EMPTY));

return yotei.state.set_val(new cljs.core.Keyword(null,"loading","loading",-737050189),false);
}));
} else {
return null;
}
});
yotei.ui.events_view = (function yotei$ui$events_view(){
var map__20132 = cljs.core.deref(yotei.state.app);
var map__20132__$1 = cljs.core.__destructure_map(map__20132);
var calendar_id = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20132__$1,new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326));
var events = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20132__$1,new cljs.core.Keyword(null,"events","events",1792552201));
var loading = cljs.core.get.cljs$core$IFn$_invoke$arity$2(map__20132__$1,new cljs.core.Keyword(null,"loading","loading",-737050189));
return new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"h2","h2",-372662728),"Upcoming Events"], null),new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-row"], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"input","input",556931961),new cljs.core.PersistentArrayMap(null, 5, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-input",new cljs.core.Keyword(null,"type","type",1174270348),"text",new cljs.core.Keyword(null,"placeholder","placeholder",-104873083),"Calendar ID",new cljs.core.Keyword(null,"value","value",305978217),calendar_id,new cljs.core.Keyword(null,"on-change","on-change",-732046149),(function (e){
return yotei.state.set_val(new cljs.core.Keyword(null,"calendar-id","calendar-id",-1560522326),yotei.ui.input_value(e));
})], null)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-btn",new cljs.core.Keyword(null,"on-click","on-click",1632826543),yotei.ui.load_events], null),"Load"], null)], null),(cljs.core.truth_(loading)?new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-center"], null),"Loading..."], null):((cljs.core.empty_QMARK_(events))?new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-center"], null),"No upcoming events"], null):new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-stack"], null),cljs.core.doall.cljs$core$IFn$_invoke$arity$1((function (){var iter__5480__auto__ = (function yotei$ui$events_view_$_iter__20133(s__20134){
return (new cljs.core.LazySeq(null,(function (){
var s__20134__$1 = s__20134;
while(true){
var temp__5823__auto__ = cljs.core.seq(s__20134__$1);
if(temp__5823__auto__){
var s__20134__$2 = temp__5823__auto__;
if(cljs.core.chunked_seq_QMARK_(s__20134__$2)){
var c__5478__auto__ = cljs.core.chunk_first(s__20134__$2);
var size__5479__auto__ = cljs.core.count(c__5478__auto__);
var b__20136 = cljs.core.chunk_buffer(size__5479__auto__);
if((function (){var i__20135 = (0);
while(true){
if((i__20135 < size__5479__auto__)){
var evt = cljs.core._nth(c__5478__auto__,i__20135);
cljs.core.chunk_append(b__20136,cljs.core.with_meta(new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-card"], null),new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 3, [new cljs.core.Keyword(null,"display","display",242065432),"flex",new cljs.core.Keyword(null,"align-items","align-items",-267946462),"flex-start",new cljs.core.Keyword(null,"justify-content","justify-content",-1990475787),"space-between"], null)], null),new cljs.core.PersistentVector(null, 5, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"flex","flex",-1425124628),(1)], null)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"15px",new cljs.core.Keyword(null,"font-weight","font-weight",2085804583),(500)], null)], null),new cljs.core.Keyword(null,"title","title",636505583).cljs$core$IFn$_invoke$arity$1(evt)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-muted",new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"13px",new cljs.core.Keyword(null,"margin-top","margin-top",392161226),"2px"], null)], null),[yotei.ui.fmt_dt(new cljs.core.Keyword(null,"start-at","start-at",-103334680).cljs$core$IFn$_invoke$arity$1(evt))," \u2014 ",yotei.ui.fmt_dt(new cljs.core.Keyword(null,"end-at","end-at",1331226740).cljs$core$IFn$_invoke$arity$1(evt))].join('')], null),(function (){var temp__5823__auto____$1 = new cljs.core.Keyword(null,"location","location",1815599388).cljs$core$IFn$_invoke$arity$1(evt);
if(cljs.core.truth_(temp__5823__auto____$1)){
var loc = temp__5823__auto____$1;
return new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-dim",new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"11px",new cljs.core.Keyword(null,"margin-top","margin-top",392161226),"2px"], null)], null),loc], null);
} else {
return null;
}
})()], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-cancel",new cljs.core.Keyword(null,"on-click","on-click",1632826543),((function (i__20135,evt,c__5478__auto__,size__5479__auto__,b__20136,s__20134__$2,temp__5823__auto__,map__20132,map__20132__$1,calendar_id,events,loading){
return (function (_){
return yotei.ui.cancel_event(new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(evt));
});})(i__20135,evt,c__5478__auto__,size__5479__auto__,b__20136,s__20134__$2,temp__5823__auto__,map__20132,map__20132__$1,calendar_id,events,loading))
], null),"Cancel"], null)], null)], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(evt)], null)));

var G__20153 = (i__20135 + (1));
i__20135 = G__20153;
continue;
} else {
return true;
}
break;
}
})()){
return cljs.core.chunk_cons(cljs.core.chunk(b__20136),yotei$ui$events_view_$_iter__20133(cljs.core.chunk_rest(s__20134__$2)));
} else {
return cljs.core.chunk_cons(cljs.core.chunk(b__20136),null);
}
} else {
var evt = cljs.core.first(s__20134__$2);
return cljs.core.cons(cljs.core.with_meta(new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-card"], null),new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 3, [new cljs.core.Keyword(null,"display","display",242065432),"flex",new cljs.core.Keyword(null,"align-items","align-items",-267946462),"flex-start",new cljs.core.Keyword(null,"justify-content","justify-content",-1990475787),"space-between"], null)], null),new cljs.core.PersistentVector(null, 5, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"flex","flex",-1425124628),(1)], null)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"15px",new cljs.core.Keyword(null,"font-weight","font-weight",2085804583),(500)], null)], null),new cljs.core.Keyword(null,"title","title",636505583).cljs$core$IFn$_invoke$arity$1(evt)], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-muted",new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"13px",new cljs.core.Keyword(null,"margin-top","margin-top",392161226),"2px"], null)], null),[yotei.ui.fmt_dt(new cljs.core.Keyword(null,"start-at","start-at",-103334680).cljs$core$IFn$_invoke$arity$1(evt))," \u2014 ",yotei.ui.fmt_dt(new cljs.core.Keyword(null,"end-at","end-at",1331226740).cljs$core$IFn$_invoke$arity$1(evt))].join('')], null),(function (){var temp__5823__auto____$1 = new cljs.core.Keyword(null,"location","location",1815599388).cljs$core$IFn$_invoke$arity$1(evt);
if(cljs.core.truth_(temp__5823__auto____$1)){
var loc = temp__5823__auto____$1;
return new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-dim",new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"font-size","font-size",-1847940346),"11px",new cljs.core.Keyword(null,"margin-top","margin-top",392161226),"2px"], null)], null),loc], null);
} else {
return null;
}
})()], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-cancel",new cljs.core.Keyword(null,"on-click","on-click",1632826543),((function (evt,s__20134__$2,temp__5823__auto__,map__20132,map__20132__$1,calendar_id,events,loading){
return (function (_){
return yotei.ui.cancel_event(new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(evt));
});})(evt,s__20134__$2,temp__5823__auto__,map__20132,map__20132__$1,calendar_id,events,loading))
], null),"Cancel"], null)], null)], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),new cljs.core.Keyword(null,"id","id",-1388402092).cljs$core$IFn$_invoke$arity$1(evt)], null)),yotei$ui$events_view_$_iter__20133(cljs.core.rest(s__20134__$2)));
}
} else {
return null;
}
break;
}
}),null,null));
});
return iter__5480__auto__(events);
})())], null)))], null);
});
yotei.ui.tab_bar = (function yotei$ui$tab_bar(){
var route = new cljs.core.Keyword(null,"route","route",329891309).cljs$core$IFn$_invoke$arity$1(cljs.core.deref(yotei.state.app));
var tabs = new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"calendar","calendar",62308146),"\uD83D\uDCC5","Calendar"], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"booking","booking",-1944315008),"\uD83D\uDCCB","Book"], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"events","events",1792552201),"\uD83D\uDCC6","Events"], null)], null);
return new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"nav","nav",719540477),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-nav"], null),cljs.core.doall.cljs$core$IFn$_invoke$arity$1((function (){var iter__5480__auto__ = (function yotei$ui$tab_bar_$_iter__20137(s__20138){
return (new cljs.core.LazySeq(null,(function (){
var s__20138__$1 = s__20138;
while(true){
var temp__5823__auto__ = cljs.core.seq(s__20138__$1);
if(temp__5823__auto__){
var s__20138__$2 = temp__5823__auto__;
if(cljs.core.chunked_seq_QMARK_(s__20138__$2)){
var c__5478__auto__ = cljs.core.chunk_first(s__20138__$2);
var size__5479__auto__ = cljs.core.count(c__5478__auto__);
var b__20140 = cljs.core.chunk_buffer(size__5479__auto__);
if((function (){var i__20139 = (0);
while(true){
if((i__20139 < size__5479__auto__)){
var vec__20141 = cljs.core._nth(c__5478__auto__,i__20139);
var id = cljs.core.nth.cljs$core$IFn$_invoke$arity$3(vec__20141,(0),null);
var icon = cljs.core.nth.cljs$core$IFn$_invoke$arity$3(vec__20141,(1),null);
var label = cljs.core.nth.cljs$core$IFn$_invoke$arity$3(vec__20141,(2),null);
cljs.core.chunk_append(b__20140,cljs.core.with_meta(new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),["yt-tab ",((cljs.core._EQ_.cljs$core$IFn$_invoke$arity$2(route,id))?"yt-tab-active":"yt-tab-idle")].join(''),new cljs.core.Keyword(null,"on-click","on-click",1632826543),((function (i__20139,vec__20141,id,icon,label,c__5478__auto__,size__5479__auto__,b__20140,s__20138__$2,temp__5823__auto__,route,tabs){
return (function (_){
return yotei.state.set_val(new cljs.core.Keyword(null,"route","route",329891309),id);
});})(i__20139,vec__20141,id,icon,label,c__5478__auto__,size__5479__auto__,b__20140,s__20138__$2,temp__5823__auto__,route,tabs))
], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"icon"], null),icon], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"label"], null),label], null)], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),id], null)));

var G__20154 = (i__20139 + (1));
i__20139 = G__20154;
continue;
} else {
return true;
}
break;
}
})()){
return cljs.core.chunk_cons(cljs.core.chunk(b__20140),yotei$ui$tab_bar_$_iter__20137(cljs.core.chunk_rest(s__20138__$2)));
} else {
return cljs.core.chunk_cons(cljs.core.chunk(b__20140),null);
}
} else {
var vec__20144 = cljs.core.first(s__20138__$2);
var id = cljs.core.nth.cljs$core$IFn$_invoke$arity$3(vec__20144,(0),null);
var icon = cljs.core.nth.cljs$core$IFn$_invoke$arity$3(vec__20144,(1),null);
var label = cljs.core.nth.cljs$core$IFn$_invoke$arity$3(vec__20144,(2),null);
return cljs.core.cons(cljs.core.with_meta(new cljs.core.PersistentVector(null, 4, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"button","button",1456579943),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),["yt-tab ",((cljs.core._EQ_.cljs$core$IFn$_invoke$arity$2(route,id))?"yt-tab-active":"yt-tab-idle")].join(''),new cljs.core.Keyword(null,"on-click","on-click",1632826543),((function (vec__20144,id,icon,label,s__20138__$2,temp__5823__auto__,route,tabs){
return (function (_){
return yotei.state.set_val(new cljs.core.Keyword(null,"route","route",329891309),id);
});})(vec__20144,id,icon,label,s__20138__$2,temp__5823__auto__,route,tabs))
], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"icon"], null),icon], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"label"], null),label], null)], null),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"key","key",-1516042587),id], null)),yotei$ui$tab_bar_$_iter__20137(cljs.core.rest(s__20138__$2)));
}
} else {
return null;
}
break;
}
}),null,null));
});
return iter__5480__auto__(tabs);
})())], null);
});
yotei.ui.root_view = (function yotei$ui$root_view(){
var route = new cljs.core.Keyword(null,"route","route",329891309).cljs$core$IFn$_invoke$arity$1(cljs.core.deref(yotei.state.app));
return new cljs.core.PersistentVector(null, 6, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-root"], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"header","header",119441134),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-header"], null),new cljs.core.PersistentVector(null, 2, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"span","span",1394872991),"Yotei"], null)], null),(function (){var temp__5823__auto__ = new cljs.core.Keyword(null,"error","error",-978969032).cljs$core$IFn$_invoke$arity$1(cljs.core.deref(yotei.state.app));
if(cljs.core.truth_(temp__5823__auto__)){
var err = temp__5823__auto__;
return new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 2, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-center",new cljs.core.Keyword(null,"style","style",-496642736),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"color","color",1011675173),"#fca5a5"], null)], null),["Error: ",cljs.core.str.cljs$core$IFn$_invoke$arity$1(err)].join('')], null);
} else {
return null;
}
})(),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"main","main",-2117802661),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-main"], null),new cljs.core.PersistentVector(null, 3, 5, cljs.core.PersistentVector.EMPTY_NODE, [new cljs.core.Keyword(null,"div","div",1057191632),new cljs.core.PersistentArrayMap(null, 1, [new cljs.core.Keyword(null,"class","class",-2030961996),"yt-content"], null),(function (){var G__20147 = route;
var G__20147__$1 = (((G__20147 instanceof cljs.core.Keyword))?G__20147.fqn:null);
switch (G__20147__$1) {
case "calendar":
return new cljs.core.PersistentVector(null, 1, 5, cljs.core.PersistentVector.EMPTY_NODE, [yotei.ui.calendar_view], null);

break;
case "booking":
return new cljs.core.PersistentVector(null, 1, 5, cljs.core.PersistentVector.EMPTY_NODE, [yotei.ui.booking_view], null);

break;
default:
return new cljs.core.PersistentVector(null, 1, 5, cljs.core.PersistentVector.EMPTY_NODE, [yotei.ui.events_view], null);

}
})()], null)], null),new cljs.core.PersistentVector(null, 1, 5, cljs.core.PersistentVector.EMPTY_NODE, [yotei.ui.tab_bar], null)], null);
});

//# sourceMappingURL=yotei.ui.js.map
