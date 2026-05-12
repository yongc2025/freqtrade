import{L as e,Mt as t,_ as n,d as r,dt as i,g as a,jt as o,kt as s,lt as c,ot as l,q as u,st as d,tt as f,v as p,yt as ee}from"./settings-BJT4_MLI.js";import{$ as m,B as h,E as g,Ft as _,L as te,P as v,R as y,V as b,_ as ne,at as x,c as S,d as C,et as w,f as T,g as E,h as D,l as O,ot as re,r as k,u as A,ut as ie,vt as j,zt as ae}from"./runtime-core.esm-bundler-bePl7dj1.js";import{l as oe,t as M}from"./inputtext-CBiCk8Q5.js";import{n as N}from"./ftbotwrapper-mm24QfGo.js";import{Y as P,d as F,o as I,p as L}from"./index-C1SCsXl-.js";import{r as R}from"./column-GO_nY-BD.js";import{n as z,r as B}from"./InfoBox-BXshHoU7.js";var V=p.extend({name:`tabs`,style:`
    .p-tabs {
        display: flex;
        flex-direction: column;
    }

    .p-tablist {
        display: flex;
        position: relative;
        overflow: hidden;
        background: dt('tabs.tablist.background');
    }

    .p-tablist-viewport {
        overflow-x: auto;
        overflow-y: hidden;
        scroll-behavior: smooth;
        scrollbar-width: none;
        overscroll-behavior: contain auto;
    }

    .p-tablist-viewport::-webkit-scrollbar {
        display: none;
    }

    .p-tablist-tab-list {
        position: relative;
        display: flex;
        border-style: solid;
        border-color: dt('tabs.tablist.border.color');
        border-width: dt('tabs.tablist.border.width');
    }

    .p-tablist-content {
        flex-grow: 1;
    }

    .p-tablist-nav-button {
        all: unset;
        position: absolute !important;
        flex-shrink: 0;
        inset-block-start: 0;
        z-index: 2;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: dt('tabs.nav.button.background');
        color: dt('tabs.nav.button.color');
        width: dt('tabs.nav.button.width');
        transition:
            color dt('tabs.transition.duration'),
            outline-color dt('tabs.transition.duration'),
            box-shadow dt('tabs.transition.duration');
        box-shadow: dt('tabs.nav.button.shadow');
        outline-color: transparent;
        cursor: pointer;
    }

    .p-tablist-nav-button:focus-visible {
        z-index: 1;
        box-shadow: dt('tabs.nav.button.focus.ring.shadow');
        outline: dt('tabs.nav.button.focus.ring.width') dt('tabs.nav.button.focus.ring.style') dt('tabs.nav.button.focus.ring.color');
        outline-offset: dt('tabs.nav.button.focus.ring.offset');
    }

    .p-tablist-nav-button:hover {
        color: dt('tabs.nav.button.hover.color');
    }

    .p-tablist-prev-button {
        inset-inline-start: 0;
    }

    .p-tablist-next-button {
        inset-inline-end: 0;
    }

    .p-tablist-prev-button:dir(rtl),
    .p-tablist-next-button:dir(rtl) {
        transform: rotate(180deg);
    }

    .p-tab {
        flex-shrink: 0;
        cursor: pointer;
        user-select: none;
        position: relative;
        border-style: solid;
        white-space: nowrap;
        gap: dt('tabs.tab.gap');
        background: dt('tabs.tab.background');
        border-width: dt('tabs.tab.border.width');
        border-color: dt('tabs.tab.border.color');
        color: dt('tabs.tab.color');
        padding: dt('tabs.tab.padding');
        font-weight: dt('tabs.tab.font.weight');
        transition:
            background dt('tabs.transition.duration'),
            border-color dt('tabs.transition.duration'),
            color dt('tabs.transition.duration'),
            outline-color dt('tabs.transition.duration'),
            box-shadow dt('tabs.transition.duration');
        margin: dt('tabs.tab.margin');
        outline-color: transparent;
    }

    .p-tab:not(.p-disabled):focus-visible {
        z-index: 1;
        box-shadow: dt('tabs.tab.focus.ring.shadow');
        outline: dt('tabs.tab.focus.ring.width') dt('tabs.tab.focus.ring.style') dt('tabs.tab.focus.ring.color');
        outline-offset: dt('tabs.tab.focus.ring.offset');
    }

    .p-tab:not(.p-tab-active):not(.p-disabled):hover {
        background: dt('tabs.tab.hover.background');
        border-color: dt('tabs.tab.hover.border.color');
        color: dt('tabs.tab.hover.color');
    }

    .p-tab-active {
        background: dt('tabs.tab.active.background');
        border-color: dt('tabs.tab.active.border.color');
        color: dt('tabs.tab.active.color');
    }

    .p-tabpanels {
        background: dt('tabs.tabpanel.background');
        color: dt('tabs.tabpanel.color');
        padding: dt('tabs.tabpanel.padding');
        outline: 0 none;
    }

    .p-tabpanel:focus-visible {
        box-shadow: dt('tabs.tabpanel.focus.ring.shadow');
        outline: dt('tabs.tabpanel.focus.ring.width') dt('tabs.tabpanel.focus.ring.style') dt('tabs.tabpanel.focus.ring.color');
        outline-offset: dt('tabs.tabpanel.focus.ring.offset');
    }

    .p-tablist-active-bar {
        z-index: 1;
        display: block;
        position: absolute;
        inset-block-end: dt('tabs.active.bar.bottom');
        height: dt('tabs.active.bar.height');
        background: dt('tabs.active.bar.background');
        transition: 250ms cubic-bezier(0.35, 0, 0.25, 1);
    }
`,classes:{root:function(e){return[`p-tabs p-component`,{"p-tabs-scrollable":e.props.scrollable}]}}}),H={name:`Tabs`,extends:{name:`BaseTabs`,extends:n,props:{value:{type:[String,Number],default:void 0},lazy:{type:Boolean,default:!1},scrollable:{type:Boolean,default:!1},showNavigators:{type:Boolean,default:!0},tabindex:{type:Number,default:0},selectOnFocus:{type:Boolean,default:!1}},style:V,provide:function(){return{$pcTabs:this,$parentInstance:this}}},inheritAttrs:!1,emits:[`update:value`],data:function(){return{d_value:this.value}},watch:{value:function(e){this.d_value=e}},methods:{updateValue:function(e){this.d_value!==e&&(this.d_value=e,this.$emit(`update:value`,e))},isVertical:function(){return this.orientation===`vertical`}}};function U(e,t,n,r,i,a){return v(),T(`div`,g({class:e.cx(`root`)},e.ptmi(`root`)),[y(e.$slots,`default`)],16)}H.render=U;var W={name:`TabPanels`,extends:{name:`BaseTabPanels`,extends:n,props:{},style:p.extend({name:`tabpanels`,classes:{root:`p-tabpanels`}}),provide:function(){return{$pcTabPanels:this,$parentInstance:this}}},inheritAttrs:!1};function G(e,t,n,r,i,a){return v(),T(`div`,g({class:e.cx(`root`),role:`presentation`},e.ptmi(`root`)),[y(e.$slots,`default`)],16)}W.render=G;var K={viewBox:`0 0 24 24`,width:`1.2em`,height:`1.2em`};function q(e,t){return v(),T(`svg`,K,[...t[0]||=[O(`path`,{fill:`currentColor`,d:`M12 17a2 2 0 0 0 2-2a2 2 0 0 0-2-2a2 2 0 0 0-2 2a2 2 0 0 0 2 2m6-9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2h1V6a5 5 0 0 1 5-5a5 5 0 0 1 5 5v2zm-6-5a3 3 0 0 0-3 3v2h6V6a3 3 0 0 0-3-3`},null,-1)]])}var se=re({name:`mdi-lock`,render:q}),ce={class:`divide-y divide-surface-300 dark:divide-surface-700 divide-solid border-x border-y rounded-sm border-surface-300 dark:border-surface-700`},le=[`title`,`onClick`],ue={class:`flex items-center gap-2`},de=[`title`],fe=P(ne({__name:`PairSummary`,props:{pairlist:{},currentLocks:{default:()=>[]},trades:{},sortMethod:{default:`normal`},backtestMode:{type:Boolean,default:!1},startingBalance:{default:0}},setup(e){let t=e,n=N(),r=ie(``),i=S(()=>{let e=[];return t.pairlist.forEach(n=>{let i=t.trades.filter(e=>e.pair===n),a=t.currentLocks.filter(e=>e.pair===n),o=``,s;a.sort((e,t)=>e.lock_end_timestamp>t.lock_end_timestamp?-1:1),a.length>0&&([s]=a,o=`${I(s.lock_end_timestamp)} - ${s.side} - ${s.reason}`);let c=``,l=0,u=0;i.forEach(e=>{l+=e.profit_ratio??0,u+=e.profit_abs??0}),t.sortMethod==`profit`&&t.startingBalance&&(l=u/t.startingBalance);let d=i.length,f=d?i[0]:void 0;i.length>0&&(c=`Current profit: ${F(l)}`),f&&(c+=`\nOpen since: ${I(f.open_timestamp)}`),(r.value===``||n.toLocaleLowerCase().includes(r.value.toLocaleLowerCase()))&&e.push({pair:n,trade:f,locks:s,lockReason:o,profitString:c,profit:l,profitAbs:u,tradeCount:d})}),t.sortMethod===`profit`?e.sort((e,t)=>e.profit>t.profit?-1:1):e.sort((e,t)=>e.trade&&!t.trade?-1:e.trade&&t.trade?e.trade.trade_id>t.trade.trade_id?1:-1:!e.locks&&t.locks?-1:e.locks&&t.locks?e.locks.lock_end_timestamp>t.locks.lock_end_timestamp?1:-1:1),e});return(t,a)=>{let o=M,s=se,c=z,l=B;return v(),T(`div`,null,[O(`div`,{"label-for":`trade-filter`,class:_([`mb-2`,{"me-4":e.backtestMode,"me-2":!e.backtestMode}])},[E(o,{id:`trade-filter`,modelValue:j(r),"onUpdate:modelValue":a[0]||=e=>x(r)?r.value=e:null,type:`text`,placeholder:`Filter`,class:`w-full`},null,8,[`modelValue`])],2),O(`ul`,ce,[(v(!0),T(k,null,te(j(i),r=>(v(),T(`li`,{key:r.pair,button:``,class:_([`flex cursor-pointer last:rounded-b justify-between items-center px-1 py-1.5`,{"bg-primary dark:border-primary text-primary-contrast":r.pair===j(n).activeBot.selectedPair}]),title:`${(`formatPriceCurrency`in t?t.formatPriceCurrency:j(L))(r.profitAbs,j(n).activeBot.stakeCurrency,j(n).activeBot.stakeCurrencyDecimals)} - ${r.pair} - ${r.tradeCount} trades`,onClick:e=>j(n).activeBot.selectedPair=r.pair},[O(`div`,ue,[D(ae(r.pair)+` `,1),r.locks?(v(),T(`span`,{key:0,title:r.lockReason},[E(s)],8,de)):C(``,!0)]),r.trade&&!e.backtestMode?(v(),A(c,{key:0,trade:r.trade},null,8,[`trade`])):C(``,!0),e.backtestMode&&r.tradeCount>0?(v(),A(l,{key:1,"profit-ratio":r.profit,"stake-currency":j(n).activeBot.stakeCurrency},null,8,[`profit-ratio`,`stake-currency`])):C(``,!0)],10,le))),128))])])}}}),[[`__scopeId`,`data-v-31f40176`]]),pe=p.extend({name:`tabpanel`,classes:{root:function(e){return[`p-tabpanel`,{"p-tabpanel-active":e.instance.active}]}}}),J={name:`TabPanel`,extends:{name:`BaseTabPanel`,extends:n,props:{value:{type:[String,Number],default:void 0},as:{type:[String,Object],default:`DIV`},asChild:{type:Boolean,default:!1},header:null,headerStyle:null,headerClass:null,headerProps:null,headerActionProps:null,contentStyle:null,contentClass:null,contentProps:null,disabled:Boolean},style:pe,provide:function(){return{$pcTabPanel:this,$parentInstance:this}}},inheritAttrs:!1,inject:[`$pcTabs`],computed:{active:function(){return e(this.$pcTabs?.d_value,this.value)},id:function(){return`${this.$pcTabs?.$id}_tabpanel_${this.value}`},ariaLabelledby:function(){return`${this.$pcTabs?.$id}_tab_${this.value}`},attrs:function(){return g(this.a11yAttrs,this.ptmi(`root`,this.ptParams))},a11yAttrs:function(){return{id:this.id,tabindex:this.$pcTabs?.tabindex,role:`tabpanel`,"aria-labelledby":this.ariaLabelledby,"data-pc-name":`tabpanel`,"data-p-active":this.active}},ptParams:function(){return{context:{active:this.active}}}}};function me(e,t,n,r,i,a){var o,s;return a.$pcTabs?(v(),T(k,{key:1},[e.asChild?y(e.$slots,`default`,{key:1,class:_(e.cx(`root`)),active:a.active,a11yAttrs:a.a11yAttrs}):(v(),T(k,{key:0},[!((o=a.$pcTabs)!=null&&o.lazy)||a.active?w((v(),A(b(e.as),g({key:0,class:e.cx(`root`)},a.attrs),{default:m(function(){return[y(e.$slots,`default`)]}),_:3},16,[`class`])),[[oe,(s=a.$pcTabs)!=null&&s.lazy?!0:a.active]]):C(``,!0)],64))],64)):y(e.$slots,`default`,{key:0})}J.render=me;var Y={name:`ChevronLeftIcon`,extends:a};function he(e){return ye(e)||ve(e)||_e(e)||ge()}function ge(){throw TypeError(`Invalid attempt to spread non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function _e(e,t){if(e){if(typeof e==`string`)return X(e,t);var n={}.toString.call(e).slice(8,-1);return n===`Object`&&e.constructor&&(n=e.constructor.name),n===`Map`||n===`Set`?Array.from(e):n===`Arguments`||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)?X(e,t):void 0}}function ve(e){if(typeof Symbol<`u`&&e[Symbol.iterator]!=null||e[`@@iterator`]!=null)return Array.from(e)}function ye(e){if(Array.isArray(e))return X(e)}function X(e,t){(t==null||t>e.length)&&(t=e.length);for(var n=0,r=Array(t);n<t;n++)r[n]=e[n];return r}function be(e,t,n,r,i,a){return v(),T(`svg`,g({width:`14`,height:`14`,viewBox:`0 0 14 14`,fill:`none`,xmlns:`http://www.w3.org/2000/svg`},e.pti()),he(t[0]||=[O(`path`,{d:`M9.61296 13C9.50997 13.0005 9.40792 12.9804 9.3128 12.9409C9.21767 12.9014 9.13139 12.8433 9.05902 12.7701L3.83313 7.54416C3.68634 7.39718 3.60388 7.19795 3.60388 6.99022C3.60388 6.78249 3.68634 6.58325 3.83313 6.43628L9.05902 1.21039C9.20762 1.07192 9.40416 0.996539 9.60724 1.00012C9.81032 1.00371 10.0041 1.08597 10.1477 1.22959C10.2913 1.37322 10.3736 1.56698 10.3772 1.77005C10.3808 1.97313 10.3054 2.16968 10.1669 2.31827L5.49496 6.99022L10.1669 11.6622C10.3137 11.8091 10.3962 12.0084 10.3962 12.2161C10.3962 12.4238 10.3137 12.6231 10.1669 12.7701C10.0945 12.8433 10.0083 12.9014 9.91313 12.9409C9.81801 12.9804 9.71596 13.0005 9.61296 13Z`,fill:`currentColor`},null,-1)]),16)}Y.render=be;var Z={name:`TabList`,extends:{name:`BaseTabList`,extends:n,props:{},style:p.extend({name:`tablist`,classes:{root:`p-tablist`,content:`p-tablist-content p-tablist-viewport`,tabList:`p-tablist-tab-list`,activeBar:`p-tablist-active-bar`,prevButton:`p-tablist-prev-button p-tablist-nav-button`,nextButton:`p-tablist-next-button p-tablist-nav-button`}}),provide:function(){return{$pcTabList:this,$parentInstance:this}}},inheritAttrs:!1,inject:[`$pcTabs`],data:function(){return{isPrevButtonEnabled:!1,isNextButtonEnabled:!0}},resizeObserver:void 0,inkBarObserver:void 0,watch:{showNavigators:function(e){e?this.bindResizeObserver():this.unbindResizeObserver()},activeValue:{flush:`post`,handler:function(){this.updateInkBar(),this.bindInkBarObserver()}}},mounted:function(){var e=this;setTimeout(function(){e.updateInkBar(),e.bindInkBarObserver()},150),this.showNavigators&&(this.updateButtonState(),this.bindResizeObserver())},updated:function(){this.showNavigators&&this.updateButtonState()},beforeUnmount:function(){this.unbindResizeObserver(),this.unbindInkBarObserver()},methods:{onScroll:function(e){this.showNavigators&&this.updateButtonState(),e.preventDefault()},onPrevButtonClick:function(){var e=this.$refs.content,t=this.getVisibleButtonWidths(),n=d(e)-t,r=Math.abs(e.scrollLeft)-n*.8,a=Math.max(r,0);e.scrollLeft=i(e)?-1*a:a},onNextButtonClick:function(){var e=this.$refs.content,t=this.getVisibleButtonWidths(),n=d(e)-t,r=Math.abs(e.scrollLeft)+n*.8,a=e.scrollWidth-n,o=Math.min(r,a);e.scrollLeft=i(e)?-1*o:o},bindResizeObserver:function(){var e=this;this.resizeObserver=new ResizeObserver(function(){return e.updateButtonState()}),this.resizeObserver.observe(this.$refs.list)},unbindResizeObserver:function(){var e;(e=this.resizeObserver)==null||e.unobserve(this.$refs.list),this.resizeObserver=void 0},bindInkBarObserver:function(){var e=this;this.unbindInkBarObserver();var t=this.$refs.content,n=o(t,`[data-pc-name="tab"][data-p-active="true"]`);n&&(this.inkBarObserver=new ResizeObserver(function(){return e.updateInkBar()}),this.inkBarObserver.observe(n))},unbindInkBarObserver:function(){var e;(e=this.inkBarObserver)==null||e.disconnect(),this.inkBarObserver=void 0},updateInkBar:function(){var e=this.$refs,t=e.content,n=e.inkbar,r=e.tabs;if(n){var i=o(t,`[data-pc-name="tab"][data-p-active="true"]`);this.$pcTabs.isVertical()?(n.style.height=u(i)+`px`,n.style.top=f(i).top-f(r).top+`px`):(n.style.width=s(i)+`px`,n.style.left=f(i).left-f(r).left+`px`)}},updateButtonState:function(){var e=this.$refs,t=e.list,n=e.content,r=n.scrollTop,i=n.scrollWidth,a=n.scrollHeight,o=n.offsetWidth,s=n.offsetHeight,l=Math.abs(n.scrollLeft),u=[d(n),c(n)],f=u[0],p=u[1];this.$pcTabs.isVertical()?(this.isPrevButtonEnabled=r!==0,this.isNextButtonEnabled=t.offsetHeight>=s&&parseInt(r)!==a-p):(this.isPrevButtonEnabled=l!==0,this.isNextButtonEnabled=t.offsetWidth>=o&&parseInt(l)!==i-f)},getVisibleButtonWidths:function(){var e=this.$refs,t=e.prevButton,n=e.nextButton,r=0;return this.showNavigators&&(r=(t?.offsetWidth||0)+(n?.offsetWidth||0)),r}},computed:{templates:function(){return this.$pcTabs.$slots},activeValue:function(){return this.$pcTabs.d_value},showNavigators:function(){return this.$pcTabs.showNavigators},prevButtonAriaLabel:function(){return this.$primevue.config.locale.aria?this.$primevue.config.locale.aria.previous:void 0},nextButtonAriaLabel:function(){return this.$primevue.config.locale.aria?this.$primevue.config.locale.aria.next:void 0},dataP:function(){return t({scrollable:this.$pcTabs.scrollable})}},components:{ChevronLeftIcon:Y,ChevronRightIcon:R},directives:{ripple:r}},xe=[`data-p`],Se=[`aria-label`,`tabindex`],Ce=[`data-p`],we=[`aria-orientation`],Q=[`aria-label`,`tabindex`];function Te(e,t,n,r,i,a){var o=h(`ripple`);return v(),T(`div`,g({ref:`list`,class:e.cx(`root`),"data-p":a.dataP},e.ptmi(`root`)),[a.showNavigators&&i.isPrevButtonEnabled?w((v(),T(`button`,g({key:0,ref:`prevButton`,type:`button`,class:e.cx(`prevButton`),"aria-label":a.prevButtonAriaLabel,tabindex:a.$pcTabs.tabindex,onClick:t[0]||=function(){return a.onPrevButtonClick&&a.onPrevButtonClick.apply(a,arguments)}},e.ptm(`prevButton`),{"data-pc-group-section":`navigator`}),[(v(),A(b(a.templates.previcon||`ChevronLeftIcon`),g({"aria-hidden":`true`},e.ptm(`prevIcon`)),null,16))],16,Se)),[[o]]):C(``,!0),O(`div`,g({ref:`content`,class:e.cx(`content`),onScroll:t[1]||=function(){return a.onScroll&&a.onScroll.apply(a,arguments)},"data-p":a.dataP},e.ptm(`content`)),[O(`div`,g({ref:`tabs`,class:e.cx(`tabList`),role:`tablist`,"aria-orientation":a.$pcTabs.orientation||`horizontal`},e.ptm(`tabList`)),[y(e.$slots,`default`),O(`span`,g({ref:`inkbar`,class:e.cx(`activeBar`),role:`presentation`,"aria-hidden":`true`},e.ptm(`activeBar`)),null,16)],16,we)],16,Ce),a.showNavigators&&i.isNextButtonEnabled?w((v(),T(`button`,g({key:1,ref:`nextButton`,type:`button`,class:e.cx(`nextButton`),"aria-label":a.nextButtonAriaLabel,tabindex:a.$pcTabs.tabindex,onClick:t[2]||=function(){return a.onNextButtonClick&&a.onNextButtonClick.apply(a,arguments)}},e.ptm(`nextButton`),{"data-pc-group-section":`navigator`}),[(v(),A(b(a.templates.nexticon||`ChevronRightIcon`),g({"aria-hidden":`true`},e.ptm(`nextIcon`)),null,16))],16,Q)),[[o]]):C(``,!0)],16,xe)}Z.render=Te;var Ee=p.extend({name:`tab`,classes:{root:function(e){var t=e.instance,n=e.props;return[`p-tab`,{"p-tab-active":t.active,"p-disabled":n.disabled}]}}}),$={name:`Tab`,extends:{name:`BaseTab`,extends:n,props:{value:{type:[String,Number],default:void 0},disabled:{type:Boolean,default:!1},as:{type:[String,Object],default:`BUTTON`},asChild:{type:Boolean,default:!1}},style:Ee,provide:function(){return{$pcTab:this,$parentInstance:this}}},inheritAttrs:!1,inject:[`$pcTabs`,`$pcTabList`],methods:{onFocus:function(){this.$pcTabs.selectOnFocus&&this.changeActiveValue()},onClick:function(){this.changeActiveValue()},onKeydown:function(e){switch(e.code){case`ArrowRight`:this.onArrowRightKey(e);break;case`ArrowLeft`:this.onArrowLeftKey(e);break;case`Home`:this.onHomeKey(e);break;case`End`:this.onEndKey(e);break;case`PageDown`:this.onPageDownKey(e);break;case`PageUp`:this.onPageUpKey(e);break;case`Enter`:case`NumpadEnter`:case`Space`:this.onEnterKey(e);break}},onArrowRightKey:function(e){var t=this.findNextTab(e.currentTarget);t?this.changeFocusedTab(e,t):this.onHomeKey(e),e.preventDefault()},onArrowLeftKey:function(e){var t=this.findPrevTab(e.currentTarget);t?this.changeFocusedTab(e,t):this.onEndKey(e),e.preventDefault()},onHomeKey:function(e){var t=this.findFirstTab();this.changeFocusedTab(e,t),e.preventDefault()},onEndKey:function(e){var t=this.findLastTab();this.changeFocusedTab(e,t),e.preventDefault()},onPageDownKey:function(e){this.scrollInView(this.findLastTab()),e.preventDefault()},onPageUpKey:function(e){this.scrollInView(this.findFirstTab()),e.preventDefault()},onEnterKey:function(e){this.changeActiveValue()},findNextTab:function(e){var t=arguments.length>1&&arguments[1]!==void 0&&arguments[1]?e:e.nextElementSibling;return t?l(t,`data-p-disabled`)||l(t,`data-pc-section`)===`activebar`?this.findNextTab(t):o(t,`[data-pc-name="tab"]`):null},findPrevTab:function(e){var t=arguments.length>1&&arguments[1]!==void 0&&arguments[1]?e:e.previousElementSibling;return t?l(t,`data-p-disabled`)||l(t,`data-pc-section`)===`activebar`?this.findPrevTab(t):o(t,`[data-pc-name="tab"]`):null},findFirstTab:function(){return this.findNextTab(this.$pcTabList.$refs.tabs.firstElementChild,!0)},findLastTab:function(){return this.findPrevTab(this.$pcTabList.$refs.tabs.lastElementChild,!0)},changeActiveValue:function(){this.$pcTabs.updateValue(this.value)},changeFocusedTab:function(e,t){ee(t),this.scrollInView(t)},scrollInView:function(e){var t;e==null||(t=e.scrollIntoView)==null||t.call(e,{block:`nearest`})}},computed:{active:function(){return e(this.$pcTabs?.d_value,this.value)},id:function(){return`${this.$pcTabs?.$id}_tab_${this.value}`},ariaControls:function(){return`${this.$pcTabs?.$id}_tabpanel_${this.value}`},attrs:function(){return g(this.asAttrs,this.a11yAttrs,this.ptmi(`root`,this.ptParams))},asAttrs:function(){return this.as===`BUTTON`?{type:`button`,disabled:this.disabled}:void 0},a11yAttrs:function(){return{id:this.id,tabindex:this.active?this.$pcTabs.tabindex:-1,role:`tab`,"aria-selected":this.active,"aria-controls":this.ariaControls,"data-pc-name":`tab`,"data-p-disabled":this.disabled,"data-p-active":this.active,onFocus:this.onFocus,onKeydown:this.onKeydown}},ptParams:function(){return{context:{active:this.active}}},dataP:function(){return t({active:this.active})}},directives:{ripple:r}};function De(e,t,n,r,i,a){var o=h(`ripple`);return e.asChild?y(e.$slots,`default`,{key:1,dataP:a.dataP,class:_(e.cx(`root`)),active:a.active,a11yAttrs:a.a11yAttrs,onClick:a.onClick}):w((v(),A(b(e.as),g({key:0,class:e.cx(`root`),"data-p":a.dataP,onClick:a.onClick},a.attrs),{default:m(function(){return[y(e.$slots,`default`)]}),_:3},16,[`class`,`data-p`,`onClick`])),[[o]])}$.render=De;export{W as a,fe as i,Z as n,H as o,J as r,$ as t};
//# sourceMappingURL=tab--iwVJ7Kr.js.map