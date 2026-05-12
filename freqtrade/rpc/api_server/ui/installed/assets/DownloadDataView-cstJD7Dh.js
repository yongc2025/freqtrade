import{Et as e,d as t,f as n,i as r}from"./useToast-O7zy2Fch.js";import{$ as i,E as a,L as o,P as s,R as c,_ as l,at as u,c as d,d as f,et as p,f as m,g as h,h as g,l as _,ot as v,r as y,u as b,ut as x,vt as S,zt as C}from"./runtime-core.esm-bundler-bePl7dj1.js";import{i as w,l as T}from"./inputtext-BBrbwrLU.js";import{E,O as D,n as O,o as k}from"./ftbotwrapper-zSO3sDE2.js";import{n as ee,r as te,t as A}from"./pairlistConfig-CSWEo5ru.js";import{t as j}from"./message-DuAuPCkW.js";import{t as M}from"./TimeRangeSelect-BTCE-k_h.js";import{B as N,G as P,U as ne,Y as F,q as I}from"./index-CLmFeIh6.js";import{t as L}from"./inputnumber-B_NBY8x0.js";import{t as R}from"./DraggableContainer-CvQtz6B7.js";import{t as z}from"./check-bkauxzut.js";import{t as B}from"./multiselect-C6j-yErs.js";import{t as V}from"./ExchangeSelect-mV02KFcf.js";var H=n.extend({name:`progressbar`,style:`
    .p-progressbar {
        display: block;
        position: relative;
        overflow: hidden;
        height: dt('progressbar.height');
        background: dt('progressbar.background');
        border-radius: dt('progressbar.border.radius');
    }

    .p-progressbar-value {
        margin: 0;
        background: dt('progressbar.value.background');
    }

    .p-progressbar-label {
        color: dt('progressbar.label.color');
        font-size: dt('progressbar.label.font.size');
        font-weight: dt('progressbar.label.font.weight');
    }

    .p-progressbar-determinate .p-progressbar-value {
        height: 100%;
        width: 0%;
        position: absolute;
        display: none;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        transition: width 1s ease-in-out;
    }

    .p-progressbar-determinate .p-progressbar-label {
        display: inline-flex;
    }

    .p-progressbar-indeterminate .p-progressbar-value::before {
        content: '';
        position: absolute;
        background: inherit;
        inset-block-start: 0;
        inset-inline-start: 0;
        inset-block-end: 0;
        will-change: inset-inline-start, inset-inline-end;
        animation: p-progressbar-indeterminate-anim 2.1s cubic-bezier(0.65, 0.815, 0.735, 0.395) infinite;
    }

    .p-progressbar-indeterminate .p-progressbar-value::after {
        content: '';
        position: absolute;
        background: inherit;
        inset-block-start: 0;
        inset-inline-start: 0;
        inset-block-end: 0;
        will-change: inset-inline-start, inset-inline-end;
        animation: p-progressbar-indeterminate-anim-short 2.1s cubic-bezier(0.165, 0.84, 0.44, 1) infinite;
        animation-delay: 1.15s;
    }

    @keyframes p-progressbar-indeterminate-anim {
        0% {
            inset-inline-start: -35%;
            inset-inline-end: 100%;
        }
        60% {
            inset-inline-start: 100%;
            inset-inline-end: -90%;
        }
        100% {
            inset-inline-start: 100%;
            inset-inline-end: -90%;
        }
    }
    @-webkit-keyframes p-progressbar-indeterminate-anim {
        0% {
            inset-inline-start: -35%;
            inset-inline-end: 100%;
        }
        60% {
            inset-inline-start: 100%;
            inset-inline-end: -90%;
        }
        100% {
            inset-inline-start: 100%;
            inset-inline-end: -90%;
        }
    }

    @keyframes p-progressbar-indeterminate-anim-short {
        0% {
            inset-inline-start: -200%;
            inset-inline-end: 100%;
        }
        60% {
            inset-inline-start: 107%;
            inset-inline-end: -8%;
        }
        100% {
            inset-inline-start: 107%;
            inset-inline-end: -8%;
        }
    }
    @-webkit-keyframes p-progressbar-indeterminate-anim-short {
        0% {
            inset-inline-start: -200%;
            inset-inline-end: 100%;
        }
        60% {
            inset-inline-start: 107%;
            inset-inline-end: -8%;
        }
        100% {
            inset-inline-start: 107%;
            inset-inline-end: -8%;
        }
    }
`,classes:{root:function(e){var t=e.instance;return[`p-progressbar p-component`,{"p-progressbar-determinate":t.determinate,"p-progressbar-indeterminate":t.indeterminate}]},value:`p-progressbar-value`,label:`p-progressbar-label`}}),U={name:`ProgressBar`,extends:{name:`BaseProgressBar`,extends:t,props:{value:{type:Number,default:null},mode:{type:String,default:`determinate`},showValue:{type:Boolean,default:!0}},style:H,provide:function(){return{$pcProgressBar:this,$parentInstance:this}}},inheritAttrs:!1,computed:{progressStyle:function(){return{width:this.value+`%`,display:`flex`}},indeterminate:function(){return this.mode===`indeterminate`},determinate:function(){return this.mode===`determinate`},dataP:function(){return e({determinate:this.determinate,indeterminate:this.indeterminate})}}},W=[`aria-valuenow`,`data-p`],G=[`data-p`],K=[`data-p`],q=[`data-p`];function J(e,t,n,r,i,o){return s(),m(`div`,a({role:`progressbar`,class:e.cx(`root`),"aria-valuemin":`0`,"aria-valuenow":e.value,"aria-valuemax":`100`,"data-p":o.dataP},e.ptmi(`root`)),[o.determinate?(s(),m(`div`,a({key:0,class:e.cx(`value`),style:o.progressStyle,"data-p":o.dataP},e.ptm(`value`)),[e.value!=null&&e.value!==0&&e.showValue?(s(),m(`div`,a({key:0,class:e.cx(`label`),"data-p":o.dataP},e.ptm(`label`)),[c(e.$slots,`default`,{},function(){return[g(C(e.value+`%`),1)]})],16,K)):f(``,!0)],16,G)):o.indeterminate?(s(),m(`div`,a({key:1,class:e.cx(`value`),"data-p":o.dataP},e.ptm(`value`)),null,16,q)):f(``,!0)],16,W)}U.render=J;var Y={viewBox:`0 0 24 24`,width:`1.2em`,height:`1.2em`};function X(e,t){return s(),m(`svg`,Y,[...t[0]||=[_(`path`,{fill:`currentColor`,d:`M8 17v-2h8v2zm8-7l-4 4l-4-4h2.5V7h3v3zM5 3h14a2 2 0 0 1 2 2v14c0 1.11-.89 2-2 2H5a2 2 0 0 1-2-2V5c0-1.1.9-2 2-2m0 2v14h14V5z`},null,-1)]])}var Z=v({name:`mdi-download-box-outline`,render:X}),Q={class:`flex flex-row items-end gap-1`},re={class:`ms-2 w-full grow space-y-1`},ie=[`title`],$={key:1},ae={class:`flex justify-between`},oe={key:1},se={key:2,class:`w-25`},ce={key:3,class:`flex flex-col md:flex-row w-full grow gap-2`},le=l({__name:`BackgroundJobTracking`,setup(e){let{runningJobs:t,clearJobs:n}=k();return(e,a)=>{let c=Z,l=z,u=U,d=N,p=r;return s(),m(`div`,Q,[_(`ul`,re,[(s(!0),m(y,null,o(S(t),(e,t)=>(s(),m(`li`,{key:t,class:`border p-1 pb-2 rounded-sm dark:border-surface-700 border-surface-300 flex gap-2 items-center`,title:t},[e.taskStatus?.job_category===`download_data`?(s(),b(c,{key:0})):(s(),m(`span`,$,C(e.taskStatus?.job_category),1)),_(`div`,ae,[e.taskStatus?.status===`success`?(s(),b(l,{key:0,class:`text-success`,title:``})):(s(),m(`span`,oe,C(e.taskStatus?.status),1)),e.taskStatus?.progress?(s(),m(`span`,se,C(e.taskStatus?.progress),1)):f(``,!0)]),e.taskStatus?.progress?(s(),b(u,{key:2,class:`w-full grow`,value:e.taskStatus?.progress/100*100,"show-progress":``,max:100,striped:``},null,8,[`value`])):f(``,!0),e.taskStatus?.progress_tasks?(s(),m(`div`,ce,[(s(!0),m(y,null,o(Object.entries(e.taskStatus?.progress_tasks),([t,n])=>(s(),m(`div`,{key:t,class:`w-full`},[g(C(n.description)+` `,1),h(u,{class:`w-full grow`,value:Math.round(n.progress/n.total*100*100)/100,"show-progress":``,pt:{value:{class:e.taskStatus.status===`success`?`bg-emerald-500`:`bg-amber-500`}},striped:``},null,8,[`value`,`pt`])]))),128))])):f(``,!0)],8,ie))),128))]),Object.keys(S(t)).length>0?(s(),b(p,{key:0,severity:`secondary`,class:`ms-auto`,onClick:S(n)},{icon:i(()=>[h(d)]),_:1},8,[`onClick`])):f(``,!0)])}}}),ue=x([{description:`All USDT Pairs`,pairs:[`.*/USDT`]},{description:`All USDT Futures Pairs`,pairs:[`.*/USDT:USDT`]}]);function de(){return{pairTemplates:d(()=>ue.value.map((e,t)=>({...e,idx:t})))}}var fe={class:`px-1 mx-auto w-full max-w-4xl lg:max-w-7xl`},pe={class:`flex mb-3 gap-3 flex-col`},me={class:`flex flex-col gap-3`},he={class:`flex flex-col lg:flex-row gap-3`},ge={class:`flex-fill`},_e={class:`flex flex-col gap-2`},ve={class:`flex gap-2`},ye={class:`flex flex-col gap-1`},be={class:`flex flex-col gap-1`},xe={class:`flex-fill px-3`},Se={class:`flex flex-col gap-2`},Ce={class:`px-3 border dark:border-surface-700 border-surface-300 p-2 rounded-sm`},we={class:`flex flex-col gap-2`},Te={class:`flex justify-between items-center`},Ee={key:0},De={key:1,class:`flex items-center gap-2`},Oe={class:`mb-2 border dark:border-surface-700 border-surface-300 rounded-sm p-2 text-start`},ke={class:`mb-2 border dark:border-surface-700 border-surface-300 rounded-md p-2 text-start`},Ae={class:`grid grid-cols md:grid-cols-2 items-center gap-2`},je={class:`mb-2 border dark:border-surface-700 border-surface-300 rounded-md p-2 text-start`},Me={class:`px-3`},Ne=l({__name:`DownloadDataMain`,setup(e){let t=O(),n=A(),a=x([`BTC/USDT`,`ETH/USDT`,``]),c=x([`5m`,`1h`]),l=x({useCustomTimerange:!1,timerange:``,days:30}),{pairTemplates:d}=de(),v=x({customExchange:!1,selectedExchange:{exchange:`binance`,trade_mode:{margin_mode:E.NONE,trading_mode:D.SPOT}}}),k=x({erase:!1,prepend_data:!1,downloadTrades:!1,candleTypes:[]}),N=x(!1),F=[{text:`Spot`,value:`spot`},{text:`Futures`,value:`futures`},{text:`Funding Rate`,value:`funding_rate`},{text:`Mark`,value:`mark`},{text:`Index`,value:`index`},{text:`Premium Index`,value:`premiumIndex`}];function z(e){a.value.push(...e)}function H(e){a.value=[...e]}async function U(){let e={pairs:a.value.filter(e=>e!==``),timeframes:c.value.filter(e=>e!==``)};l.value.useCustomTimerange&&l.value.timerange?e.timerange=l.value.timerange:e.days=l.value.days,N.value&&(e.erase=k.value.erase,e.download_trades=k.value.downloadTrades,v.value.customExchange&&(e.exchange=v.value.selectedExchange.exchange,e.trading_mode=v.value.selectedExchange.trade_mode.trading_mode,e.margin_mode=v.value.selectedExchange.trade_mode.margin_mode),t.activeBot.botFeatures.downloadDataCandleTypes&&k.value.candleTypes.length>0&&(e.candle_types=k.value.candleTypes),t.activeBot.botFeatures.downloadDataPrepend&&k.value.prepend_data&&(e.prepend_data=!0)),await t.activeBot.startDataDownload(e)}return(e,x)=>{let E=le,D=ee,O=r,A=I,W=P,G=M,K=L,q=ne,J=te,Y=j,X=B,Z=V,Q=R;return s(),m(`div`,fe,[h(E,{class:`mb-4`}),h(Q,{header:`Downloading Data`,class:`mx-1 p-4`},{default:i(()=>[_(`div`,pe,[_(`div`,me,[_(`div`,he,[_(`div`,ge,[_(`div`,_e,[x[14]||=_(`div`,{class:`flex justify-between`},[_(`h4`,{class:`text-start font-bold text-lg`},`Select Pairs`),_(`h5`,{class:`text-start font-bold text-lg`},`Pairs from template`)],-1),_(`div`,ve,[h(D,{modelValue:S(a),"onUpdate:modelValue":x[0]||=e=>u(a)?a.value=e:null,placeholder:`Pair`,size:`small`,class:`grow`},null,8,[`modelValue`]),_(`div`,ye,[_(`div`,be,[(s(!0),m(y,null,o(S(d),e=>(s(),b(O,{key:e.idx,severity:`secondary`,title:e.pairs.reduce((e,t)=>`${e}${t}\n`,``),onClick:t=>z(e.pairs)},{default:i(()=>[g(C(e.description),1)]),_:2},1032,[`title`,`onClick`]))),128))]),h(A),h(O,{disabled:S(n).whitelist.length===0,title:`Add all pairs from Pairlist Config - requires the pairlist config to have ran first.`,severity:`secondary`,onClick:x[1]||=e=>H(S(n).whitelist)},{default:i(()=>[...x[13]||=[g(` Use Pairs from Pairlist Config `,-1)]]),_:1},8,[`disabled`])])])])]),_(`div`,xe,[_(`div`,Se,[x[15]||=_(`h4`,{class:`text-start font-bold text-lg`},`Select timeframes`,-1),h(D,{modelValue:S(c),"onUpdate:modelValue":x[2]||=e=>u(c)?c.value=e:null,placeholder:`Timeframe`},null,8,[`modelValue`])])])]),_(`div`,Ce,[_(`div`,we,[_(`div`,Te,[x[17]||=_(`h4`,{class:`text-start mb-0 font-bold text-lg`},`Time Selection`,-1),h(W,{modelValue:S(l).useCustomTimerange,"onUpdate:modelValue":x[3]||=e=>S(l).useCustomTimerange=e,class:`mb-0`,switch:``},{default:i(()=>[...x[16]||=[g(` Use custom timerange `,-1)]]),_:1},8,[`modelValue`])]),S(l).useCustomTimerange?(s(),m(`div`,Ee,[h(G,{modelValue:S(l).timerange,"onUpdate:modelValue":x[4]||=e=>S(l).timerange=e},null,8,[`modelValue`])])):(s(),m(`div`,De,[x[18]||=_(`label`,null,`Days to download:`,-1),h(K,{modelValue:S(l).days,"onUpdate:modelValue":x[5]||=e=>S(l).days=e,type:`number`,"aria-label":`Days to download`,min:1,step:1,size:`small`},null,8,[`modelValue`])]))])]),_(`div`,Oe,[h(O,{class:`mb-2`,severity:`secondary`,onClick:x[6]||=e=>N.value=!S(N)},{default:i(()=>[x[19]||=g(` Advanced Options `,-1),S(N)?(s(),b(J,{key:1})):(s(),b(q,{key:0}))]),_:1}),h(w,null,{default:i(()=>[p(_(`div`,null,[h(Y,{severity:`info`,class:`mb-2 py-2`},{default:i(()=>[...x[20]||=[g(` Advanced options (Erase data, Download trades, and Custom Exchange settings) will only be applied when this section is expanded. `,-1)]]),_:1}),_(`div`,ke,[h(W,{modelValue:S(k).erase,"onUpdate:modelValue":x[7]||=e=>S(k).erase=e,class:`mb-2`},{default:i(()=>[...x[21]||=[g(`Erase existing data`,-1)]]),_:1},8,[`modelValue`]),S(t).activeBot.botFeatures.downloadDataPrepend?(s(),b(W,{key:0,modelValue:S(k).prepend_data,"onUpdate:modelValue":x[8]||=e=>S(k).prepend_data=e,class:`mb-2`},{default:i(()=>[...x[22]||=[g(`Prepend data when downloading`,-1)]]),_:1},8,[`modelValue`])):f(``,!0),h(W,{modelValue:S(k).downloadTrades,"onUpdate:modelValue":x[9]||=e=>S(k).downloadTrades=e,class:`mb-2`},{default:i(()=>[...x[23]||=[g(` Download Trades instead of OHLCV data `,-1)]]),_:1},8,[`modelValue`]),_(`div`,Ae,[S(t).activeBot.botFeatures.downloadDataCandleTypes?(s(),b(X,{key:0,modelValue:S(k).candleTypes,"onUpdate:modelValue":x[10]||=e=>S(k).candleTypes=e,options:F,"option-label":`text`,"option-value":`value`,placeholder:`Select Candle Types`},null,8,[`modelValue`])):f(``,!0),x[24]||=_(`small`,null,`When no candle-type is selected, freqtrade will download the necessary candle types for regular operation automatically.`,-1)])]),_(`div`,je,[h(W,{modelValue:S(v).customExchange,"onUpdate:modelValue":x[11]||=e=>S(v).customExchange=e,class:`mb-2`},{default:i(()=>[...x[25]||=[g(` Custom Exchange `,-1)]]),_:1},8,[`modelValue`]),h(w,{name:`fade`},{default:i(()=>[p(h(Z,{modelValue:S(v).selectedExchange,"onUpdate:modelValue":x[12]||=e=>S(v).selectedExchange=e},null,8,[`modelValue`]),[[T,S(v).customExchange]])]),_:1})])],512),[[T,S(N)]])]),_:1})]),_(`div`,Me,[h(O,{severity:`primary`,onClick:U},{default:i(()=>[...x[26]||=[g(`Start Download`,-1)]]),_:1})])])])]),_:1})])}}}),Pe={};function Fe(e,t){let n=Ne;return s(),b(n,{class:`pt-4`})}var Ie=F(Pe,[[`render`,Fe]]);export{Ie as default};
//# sourceMappingURL=DownloadDataView-cstJD7Dh.js.map