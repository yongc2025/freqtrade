import{Ct as e,E as t,Et as n,H as r,I as i,K as a,M as o,P as s,T as c,Tt as l,X as u,a as d,d as f,f as p,ft as m,j as h,l as ee,lt as te,nt as ne,pt as g,wt as re}from"./useToast-O7zy2Fch.js";import{$ as _,B as ie,E as v,Ft as y,L as b,Lt as ae,P as x,R as S,V as C,d as w,et as oe,f as T,g as E,h as D,l as O,m as se,r as k,u as A,z as j,zt as M}from"./runtime-core.esm-bundler-bePl7dj1.js";import{i as ce,n as le,t as ue}from"./inputtext-BBrbwrLU.js";import{n as N,t as de}from"./portal-CQt5ohyV.js";import{a as P,d as F,i as I,n as L,o as R,r as z,u as B}from"./select-DGCOWd_f.js";import{t as V}from"./times-DnOROSFM.js";import{t as H}from"./checkbox-DY17IWXO.js";import{n as fe,t as pe}from"./overlayeventbus-CM_XvPqh.js";import{J as me}from"./index-CLmFeIh6.js";var he=p.extend({name:`chip`,style:`
    .p-chip {
        display: inline-flex;
        align-items: center;
        background: dt('chip.background');
        color: dt('chip.color');
        border-radius: dt('chip.border.radius');
        padding-block: dt('chip.padding.y');
        padding-inline: dt('chip.padding.x');
        gap: dt('chip.gap');
    }

    .p-chip-icon {
        color: dt('chip.icon.color');
        font-size: dt('chip.icon.size');
        width: dt('chip.icon.size');
        height: dt('chip.icon.size');
    }

    .p-chip-image {
        border-radius: 50%;
        width: dt('chip.image.width');
        height: dt('chip.image.height');
        margin-inline-start: calc(-1 * dt('chip.padding.y'));
    }

    .p-chip:has(.p-chip-remove-icon) {
        padding-inline-end: dt('chip.padding.y');
    }

    .p-chip:has(.p-chip-image) {
        padding-block-start: calc(dt('chip.padding.y') / 2);
        padding-block-end: calc(dt('chip.padding.y') / 2);
    }

    .p-chip-remove-icon {
        cursor: pointer;
        font-size: dt('chip.remove.icon.size');
        width: dt('chip.remove.icon.size');
        height: dt('chip.remove.icon.size');
        color: dt('chip.remove.icon.color');
        border-radius: 50%;
        transition:
            outline-color dt('chip.transition.duration'),
            box-shadow dt('chip.transition.duration');
        outline-color: transparent;
    }

    .p-chip-remove-icon:focus-visible {
        box-shadow: dt('chip.remove.icon.focus.ring.shadow');
        outline: dt('chip.remove.icon.focus.ring.width') dt('chip.remove.icon.focus.ring.style') dt('chip.remove.icon.focus.ring.color');
        outline-offset: dt('chip.remove.icon.focus.ring.offset');
    }
`,classes:{root:`p-chip p-component`,image:`p-chip-image`,icon:`p-chip-icon`,label:`p-chip-label`,removeIcon:`p-chip-remove-icon`}}),U={name:`Chip`,extends:{name:`BaseChip`,extends:f,props:{label:{type:[String,Number],default:null},icon:{type:String,default:null},image:{type:String,default:null},removable:{type:Boolean,default:!1},removeIcon:{type:String,default:void 0}},style:he,provide:function(){return{$pcChip:this,$parentInstance:this}}},inheritAttrs:!1,emits:[`remove`],data:function(){return{visible:!0}},methods:{onKeydown:function(e){(e.key===`Enter`||e.key===`Backspace`)&&this.close(e)},close:function(e){this.visible=!1,this.$emit(`remove`,e)}},computed:{dataP:function(){return n({removable:this.removable})}},components:{TimesCircleIcon:me}},ge=[`aria-label`,`data-p`],_e=[`src`];function ve(e,t,n,r,i,a){return i.visible?(x(),T(`div`,v({key:0,class:e.cx(`root`),"aria-label":e.label},e.ptmi(`root`),{"data-p":a.dataP}),[S(e.$slots,`default`,{},function(){return[e.image?(x(),T(`img`,v({key:0,src:e.image},e.ptm(`image`),{class:e.cx(`image`)}),null,16,_e)):e.$slots.icon?(x(),A(C(e.$slots.icon),v({key:1,class:e.cx(`icon`)},e.ptm(`icon`)),null,16,[`class`])):e.icon?(x(),T(`span`,v({key:2,class:[e.cx(`icon`),e.icon]},e.ptm(`icon`)),null,16)):w(``,!0),e.label===null?w(``,!0):(x(),T(`div`,v({key:3,class:e.cx(`label`)},e.ptm(`label`)),M(e.label),17))]}),e.removable?S(e.$slots,`removeicon`,{key:0,removeCallback:a.close,keydownCallback:a.onKeydown},function(){return[(x(),A(C(e.removeIcon?`span`:`TimesCircleIcon`),v({class:[e.cx(`removeIcon`),e.removeIcon],onClick:a.close,onKeydown:a.onKeydown},e.ptm(`removeIcon`)),null,16,[`class`,`onClick`,`onKeydown`]))]}):w(``,!0)],16,ge)):w(``,!0)}U.render=ve;var ye=p.extend({name:`multiselect`,style:`
    .p-multiselect {
        display: inline-flex;
        cursor: pointer;
        position: relative;
        user-select: none;
        background: dt('multiselect.background');
        border: 1px solid dt('multiselect.border.color');
        transition:
            background dt('multiselect.transition.duration'),
            color dt('multiselect.transition.duration'),
            border-color dt('multiselect.transition.duration'),
            outline-color dt('multiselect.transition.duration'),
            box-shadow dt('multiselect.transition.duration');
        border-radius: dt('multiselect.border.radius');
        outline-color: transparent;
        box-shadow: dt('multiselect.shadow');
    }

    .p-multiselect:not(.p-disabled):hover {
        border-color: dt('multiselect.hover.border.color');
    }

    .p-multiselect:not(.p-disabled).p-focus {
        border-color: dt('multiselect.focus.border.color');
        box-shadow: dt('multiselect.focus.ring.shadow');
        outline: dt('multiselect.focus.ring.width') dt('multiselect.focus.ring.style') dt('multiselect.focus.ring.color');
        outline-offset: dt('multiselect.focus.ring.offset');
    }

    .p-multiselect.p-variant-filled {
        background: dt('multiselect.filled.background');
    }

    .p-multiselect.p-variant-filled:not(.p-disabled):hover {
        background: dt('multiselect.filled.hover.background');
    }

    .p-multiselect.p-variant-filled.p-focus {
        background: dt('multiselect.filled.focus.background');
    }

    .p-multiselect.p-invalid {
        border-color: dt('multiselect.invalid.border.color');
    }

    .p-multiselect.p-disabled {
        opacity: 1;
        background: dt('multiselect.disabled.background');
    }

    .p-multiselect-dropdown {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        background: transparent;
        color: dt('multiselect.dropdown.color');
        width: dt('multiselect.dropdown.width');
        border-start-end-radius: dt('multiselect.border.radius');
        border-end-end-radius: dt('multiselect.border.radius');
    }

    .p-multiselect-clear-icon {
        align-self: center;
        color: dt('multiselect.clear.icon.color');
        inset-inline-end: dt('multiselect.dropdown.width');
    }

    .p-multiselect-label-container {
        overflow: hidden;
        flex: 1 1 auto;
        cursor: pointer;
    }

    .p-multiselect-label {
        white-space: nowrap;
        cursor: pointer;
        overflow: hidden;
        text-overflow: ellipsis;
        padding: dt('multiselect.padding.y') dt('multiselect.padding.x');
        color: dt('multiselect.color');
    }

    .p-multiselect-display-chip .p-multiselect-label {
        display: flex;
        align-items: center;
        gap: calc(dt('multiselect.padding.y') / 2);
    }

    .p-multiselect-label.p-placeholder {
        color: dt('multiselect.placeholder.color');
    }

    .p-multiselect.p-invalid .p-multiselect-label.p-placeholder {
        color: dt('multiselect.invalid.placeholder.color');
    }

    .p-multiselect.p-disabled .p-multiselect-label {
        color: dt('multiselect.disabled.color');
    }

    .p-multiselect-label-empty {
        overflow: hidden;
        visibility: hidden;
    }

    .p-multiselect-overlay {
        position: absolute;
        top: 0;
        left: 0;
        background: dt('multiselect.overlay.background');
        color: dt('multiselect.overlay.color');
        border: 1px solid dt('multiselect.overlay.border.color');
        border-radius: dt('multiselect.overlay.border.radius');
        box-shadow: dt('multiselect.overlay.shadow');
        min-width: 100%;
    }

    .p-multiselect-header {
        display: flex;
        align-items: center;
        padding: dt('multiselect.list.header.padding');
    }

    .p-multiselect-header .p-checkbox {
        margin-inline-end: dt('multiselect.option.gap');
    }

    .p-multiselect-filter-container {
        flex: 1 1 auto;
    }

    .p-multiselect-filter {
        width: 100%;
    }

    .p-multiselect-list-container {
        overflow: auto;
    }

    .p-multiselect-list {
        margin: 0;
        padding: 0;
        list-style-type: none;
        padding: dt('multiselect.list.padding');
        display: flex;
        flex-direction: column;
        gap: dt('multiselect.list.gap');
    }

    .p-multiselect-option {
        cursor: pointer;
        font-weight: normal;
        white-space: nowrap;
        position: relative;
        overflow: hidden;
        display: flex;
        align-items: center;
        gap: dt('multiselect.option.gap');
        padding: dt('multiselect.option.padding');
        border: 0 none;
        color: dt('multiselect.option.color');
        background: transparent;
        transition:
            background dt('multiselect.transition.duration'),
            color dt('multiselect.transition.duration'),
            border-color dt('multiselect.transition.duration'),
            box-shadow dt('multiselect.transition.duration'),
            outline-color dt('multiselect.transition.duration');
        border-radius: dt('multiselect.option.border.radius');
    }

    .p-multiselect-option:not(.p-multiselect-option-selected):not(.p-disabled).p-focus {
        background: dt('multiselect.option.focus.background');
        color: dt('multiselect.option.focus.color');
    }

    .p-multiselect-option:not(.p-multiselect-option-selected):not(.p-disabled):hover {
        background: dt('multiselect.option.focus.background');
        color: dt('multiselect.option.focus.color');
    }

    .p-multiselect-option.p-multiselect-option-selected {
        background: dt('multiselect.option.selected.background');
        color: dt('multiselect.option.selected.color');
    }

    .p-multiselect-option.p-multiselect-option-selected.p-focus {
        background: dt('multiselect.option.selected.focus.background');
        color: dt('multiselect.option.selected.focus.color');
    }

    .p-multiselect-option-group {
        cursor: auto;
        margin: 0;
        padding: dt('multiselect.option.group.padding');
        background: dt('multiselect.option.group.background');
        color: dt('multiselect.option.group.color');
        font-weight: dt('multiselect.option.group.font.weight');
    }

    .p-multiselect-empty-message {
        padding: dt('multiselect.empty.message.padding');
    }

    .p-multiselect-label .p-chip {
        padding-block-start: calc(dt('multiselect.padding.y') / 2);
        padding-block-end: calc(dt('multiselect.padding.y') / 2);
        border-radius: dt('multiselect.chip.border.radius');
    }

    .p-multiselect-label:has(.p-chip) {
        padding: calc(dt('multiselect.padding.y') / 2) calc(dt('multiselect.padding.x') / 2);
    }

    .p-multiselect-fluid {
        display: flex;
        width: 100%;
    }

    .p-multiselect-sm .p-multiselect-label {
        font-size: dt('multiselect.sm.font.size');
        padding-block: dt('multiselect.sm.padding.y');
        padding-inline: dt('multiselect.sm.padding.x');
    }

    .p-multiselect-sm .p-multiselect-dropdown .p-icon {
        font-size: dt('multiselect.sm.font.size');
        width: dt('multiselect.sm.font.size');
        height: dt('multiselect.sm.font.size');
    }

    .p-multiselect-lg .p-multiselect-label {
        font-size: dt('multiselect.lg.font.size');
        padding-block: dt('multiselect.lg.padding.y');
        padding-inline: dt('multiselect.lg.padding.x');
    }

    .p-multiselect-lg .p-multiselect-dropdown .p-icon {
        font-size: dt('multiselect.lg.font.size');
        width: dt('multiselect.lg.font.size');
        height: dt('multiselect.lg.font.size');
    }

    .p-floatlabel-in .p-multiselect-filter {
        padding-block-start: dt('multiselect.padding.y');
        padding-block-end: dt('multiselect.padding.y');
    }
`,classes:{root:function(e){var t=e.instance,n=e.props;return[`p-multiselect p-component p-inputwrapper`,{"p-multiselect-display-chip":n.display===`chip`,"p-disabled":n.disabled,"p-invalid":t.$invalid,"p-variant-filled":t.$variant===`filled`,"p-focus":t.focused,"p-inputwrapper-filled":t.$filled,"p-inputwrapper-focus":t.focused||t.overlayVisible,"p-multiselect-open":t.overlayVisible,"p-multiselect-fluid":t.$fluid,"p-multiselect-sm p-inputfield-sm":n.size===`small`,"p-multiselect-lg p-inputfield-lg":n.size===`large`}]},labelContainer:`p-multiselect-label-container`,label:function(e){var t=e.instance,n=e.props;return[`p-multiselect-label`,{"p-placeholder":t.label===n.placeholder,"p-multiselect-label-empty":!n.placeholder&&!t.$filled}]},clearIcon:`p-multiselect-clear-icon`,chipItem:`p-multiselect-chip-item`,pcChip:`p-multiselect-chip`,chipIcon:`p-multiselect-chip-icon`,dropdown:`p-multiselect-dropdown`,loadingIcon:`p-multiselect-loading-icon`,dropdownIcon:`p-multiselect-dropdown-icon`,overlay:`p-multiselect-overlay p-component`,header:`p-multiselect-header`,pcFilterContainer:`p-multiselect-filter-container`,pcFilter:`p-multiselect-filter`,listContainer:`p-multiselect-list-container`,list:`p-multiselect-list`,optionGroup:`p-multiselect-option-group`,option:function(e){var t=e.instance,n=e.option,r=e.index,i=e.getItemOptions,a=e.props;return[`p-multiselect-option`,{"p-multiselect-option-selected":t.isSelected(n)&&a.highlightOnSelect,"p-focus":t.focusedOptionIndex===t.getOptionIndex(r,i),"p-disabled":t.isOptionDisabled(n)}]},emptyMessage:`p-multiselect-empty-message`},inlineStyles:{root:function(e){return{position:e.props.appendTo===`self`?`relative`:void 0}}}}),be={name:`BaseMultiSelect`,extends:le,props:{options:Array,optionLabel:null,optionValue:null,optionDisabled:null,optionGroupLabel:null,optionGroupChildren:null,scrollHeight:{type:String,default:`14rem`},placeholder:String,inputId:{type:String,default:null},panelClass:{type:String,default:null},panelStyle:{type:null,default:null},overlayClass:{type:String,default:null},overlayStyle:{type:null,default:null},dataKey:null,showClear:{type:Boolean,default:!1},clearIcon:{type:String,default:void 0},resetFilterOnClear:{type:Boolean,default:!1},filter:Boolean,filterPlaceholder:String,filterLocale:String,filterMatchMode:{type:String,default:`contains`},filterFields:{type:Array,default:null},appendTo:{type:[String,Object],default:`body`},display:{type:String,default:`comma`},selectedItemsLabel:{type:String,default:null},maxSelectedLabels:{type:Number,default:null},selectionLimit:{type:Number,default:null},showToggleAll:{type:Boolean,default:!0},loading:{type:Boolean,default:!1},checkboxIcon:{type:String,default:void 0},dropdownIcon:{type:String,default:void 0},filterIcon:{type:String,default:void 0},loadingIcon:{type:String,default:void 0},removeTokenIcon:{type:String,default:void 0},chipIcon:{type:String,default:void 0},selectAll:{type:Boolean,default:null},resetFilterOnHide:{type:Boolean,default:!1},virtualScrollerOptions:{type:Object,default:null},autoOptionFocus:{type:Boolean,default:!1},autoFilterFocus:{type:Boolean,default:!1},focusOnHover:{type:Boolean,default:!0},highlightOnSelect:{type:Boolean,default:!1},filterMessage:{type:String,default:null},selectionMessage:{type:String,default:null},emptySelectionMessage:{type:String,default:null},emptyFilterMessage:{type:String,default:null},emptyMessage:{type:String,default:null},tabindex:{type:Number,default:0},ariaLabel:{type:String,default:null},ariaLabelledby:{type:String,default:null}},style:ye,provide:function(){return{$pcMultiSelect:this,$parentInstance:this}}};function W(e){"@babel/helpers - typeof";return W=typeof Symbol==`function`&&typeof Symbol.iterator==`symbol`?function(e){return typeof e}:function(e){return e&&typeof Symbol==`function`&&e.constructor===Symbol&&e!==Symbol.prototype?`symbol`:typeof e},W(e)}function G(e,t){var n=Object.keys(e);if(Object.getOwnPropertySymbols){var r=Object.getOwnPropertySymbols(e);t&&(r=r.filter(function(t){return Object.getOwnPropertyDescriptor(e,t).enumerable})),n.push.apply(n,r)}return n}function K(e){for(var t=1;t<arguments.length;t++){var n=arguments[t]==null?{}:arguments[t];t%2?G(Object(n),!0).forEach(function(t){q(e,t,n[t])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(n)):G(Object(n)).forEach(function(t){Object.defineProperty(e,t,Object.getOwnPropertyDescriptor(n,t))})}return e}function q(e,t,n){return(t=xe(t))in e?Object.defineProperty(e,t,{value:n,enumerable:!0,configurable:!0,writable:!0}):e[t]=n,e}function xe(e){var t=Se(e,`string`);return W(t)==`symbol`?t:t+``}function Se(e,t){if(W(e)!=`object`||!e)return e;var n=e[Symbol.toPrimitive];if(n!==void 0){var r=n.call(e,t);if(W(r)!=`object`)return r;throw TypeError(`@@toPrimitive must return a primitive value.`)}return(t===`string`?String:Number)(e)}function J(e){return Ee(e)||Te(e)||we(e)||Ce()}function Ce(){throw TypeError(`Invalid attempt to spread non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function we(e,t){if(e){if(typeof e==`string`)return Y(e,t);var n={}.toString.call(e).slice(8,-1);return n===`Object`&&e.constructor&&(n=e.constructor.name),n===`Map`||n===`Set`?Array.from(e):n===`Arguments`||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)?Y(e,t):void 0}}function Te(e){if(typeof Symbol<`u`&&e[Symbol.iterator]!=null||e[`@@iterator`]!=null)return Array.from(e)}function Ee(e){if(Array.isArray(e))return Y(e)}function Y(e,t){(t==null||t>e.length)&&(t=e.length);for(var n=0,r=Array(t);n<t;n++)r[n]=e[n];return r}var X={name:`MultiSelect`,extends:be,inheritAttrs:!1,emits:[`change`,`focus`,`blur`,`before-show`,`before-hide`,`show`,`hide`,`filter`,`selectall-change`],inject:{$pcFluid:{default:null}},outsideClickListener:null,scrollHandler:null,resizeListener:null,overlay:null,list:null,virtualScroller:null,startRangeIndex:-1,searchTimeout:null,searchValue:``,selectOnFocus:!1,data:function(){return{clicked:!1,focused:!1,focusedOptionIndex:-1,filterValue:null,overlayVisible:!1}},watch:{options:function(){this.autoUpdateModel()}},mounted:function(){this.autoUpdateModel()},beforeUnmount:function(){this.unbindOutsideClickListener(),this.unbindResizeListener(),this.scrollHandler&&=(this.scrollHandler.destroy(),null),this.overlay&&=(N.clear(this.overlay),null)},methods:{getOptionIndex:function(e,t){return this.virtualScrollerDisabled?e:t&&t(e).index},getOptionLabel:function(e){return this.optionLabel?s(e,this.optionLabel):e},getOptionValue:function(e){return this.optionValue?s(e,this.optionValue):e},getOptionRenderKey:function(e,t){return this.dataKey?s(e,this.dataKey):this.getOptionLabel(e)+`_${t}`},getHeaderCheckboxPTOptions:function(e){return this.ptm(e,{context:{selected:this.allSelected}})},getCheckboxPTOptions:function(e,t,n,r){return this.ptm(r,{context:{selected:this.isSelected(e),focused:this.focusedOptionIndex===this.getOptionIndex(n,t),disabled:this.isOptionDisabled(e)}})},isOptionDisabled:function(e){return this.maxSelectionLimitReached&&!this.isSelected(e)?!0:this.optionDisabled?s(e,this.optionDisabled):!1},isOptionGroup:function(e){return!!(this.optionGroupLabel&&e.optionGroup&&e.group)},getOptionGroupLabel:function(e){return s(e,this.optionGroupLabel)},getOptionGroupChildren:function(e){return s(e,this.optionGroupChildren)},getAriaPosInset:function(e){var t=this;return(this.optionGroupLabel?e-this.visibleOptions.slice(0,e).filter(function(e){return t.isOptionGroup(e)}).length:e)+1},show:function(e){this.$emit(`before-show`),this.overlayVisible=!0,this.focusedOptionIndex=this.focusedOptionIndex===-1?this.autoOptionFocus?this.findFirstFocusedOptionIndex():this.findSelectedOptionIndex():this.focusedOptionIndex,e&&g(this.$refs.focusInput)},hide:function(e){var t=this,n=function(){t.$emit(`before-hide`),t.overlayVisible=!1,t.clicked=!1,t.focusedOptionIndex=-1,t.searchValue=``,t.resetFilterOnHide&&(t.filterValue=null),e&&g(t.$refs.focusInput)};setTimeout(function(){n()},0)},onFocus:function(e){this.disabled||(this.focused=!0,this.overlayVisible&&(this.focusedOptionIndex=this.focusedOptionIndex===-1?this.autoOptionFocus?this.findFirstFocusedOptionIndex():this.findSelectedOptionIndex():this.focusedOptionIndex,!this.autoFilterFocus&&this.scrollInView(this.focusedOptionIndex)),this.$emit(`focus`,e))},onBlur:function(e){var t,n;this.clicked=!1,this.focused=!1,this.focusedOptionIndex=-1,this.searchValue=``,this.$emit(`blur`,e),(t=(n=this.formField).onBlur)==null||t.call(n)},onKeyDown:function(e){var t=this;if(this.disabled){e.preventDefault();return}var n=e.metaKey||e.ctrlKey;switch(e.code){case`ArrowDown`:this.onArrowDownKey(e);break;case`ArrowUp`:this.onArrowUpKey(e);break;case`Home`:this.onHomeKey(e);break;case`End`:this.onEndKey(e);break;case`PageDown`:this.onPageDownKey(e);break;case`PageUp`:this.onPageUpKey(e);break;case`Enter`:case`NumpadEnter`:case`Space`:this.onEnterKey(e);break;case`Escape`:this.onEscapeKey(e);break;case`Tab`:this.onTabKey(e);break;case`ShiftLeft`:case`ShiftRight`:this.onShiftKey(e);break;default:if(e.code===`KeyA`&&n){var r=this.visibleOptions.filter(function(e){return t.isValidOption(e)}).map(function(e){return t.getOptionValue(e)});this.updateModel(e,r),e.preventDefault();break}!n&&c(e.key)&&(!this.overlayVisible&&this.show(),this.searchOptions(e),e.preventDefault());break}this.clicked=!1},onContainerClick:function(e){this.disabled||this.loading||e.target.tagName===`INPUT`||e.target.getAttribute(`data-pc-section`)===`clearicon`||e.target.closest(`[data-pc-section="clearicon"]`)||((!this.overlay||!this.overlay.contains(e.target))&&(this.overlayVisible?this.hide(!0):this.show(!0)),this.clicked=!0)},onClearClick:function(e){this.updateModel(e,[]),this.resetFilterOnClear&&(this.filterValue=null)},onFirstHiddenFocus:function(e){g(e.relatedTarget===this.$refs.focusInput?re(this.overlay,`:not([data-p-hidden-focusable="true"])`):this.$refs.focusInput)},onLastHiddenFocus:function(e){g(e.relatedTarget===this.$refs.focusInput?u(this.overlay,`:not([data-p-hidden-focusable="true"])`):this.$refs.focusInput)},onOptionSelect:function(e,t){var n=this,r=arguments.length>2&&arguments[2]!==void 0?arguments[2]:-1,i=arguments.length>3&&arguments[3]!==void 0?arguments[3]:!1;if(!(this.disabled||this.isOptionDisabled(t))){var a=this.isSelected(t),o=null;o=a?this.d_value.filter(function(e){return!h(e,n.getOptionValue(t),n.equalityKey)}):[].concat(J(this.d_value||[]),[this.getOptionValue(t)]),this.updateModel(e,o),r!==-1&&(this.focusedOptionIndex=r),i&&g(this.$refs.focusInput)}},onOptionMouseMove:function(e,t){this.focusOnHover&&this.changeFocusedOptionIndex(e,t)},onOptionSelectRange:function(e){var t=this,n=arguments.length>1&&arguments[1]!==void 0?arguments[1]:-1,r=arguments.length>2&&arguments[2]!==void 0?arguments[2]:-1;if(n===-1&&(n=this.findNearestSelectedOptionIndex(r,!0)),r===-1&&(r=this.findNearestSelectedOptionIndex(n)),n!==-1&&r!==-1){var i=Math.min(n,r),a=Math.max(n,r),o=this.visibleOptions.slice(i,a+1).filter(function(e){return t.isValidOption(e)}).map(function(e){return t.getOptionValue(e)});this.updateModel(e,o)}},onFilterChange:function(e){var t=e.target.value;this.filterValue=t,this.focusedOptionIndex=-1,this.$emit(`filter`,{originalEvent:e,value:t}),!this.virtualScrollerDisabled&&this.virtualScroller.scrollToIndex(0)},onFilterKeyDown:function(e){switch(e.code){case`ArrowDown`:this.onArrowDownKey(e);break;case`ArrowUp`:this.onArrowUpKey(e,!0);break;case`ArrowLeft`:case`ArrowRight`:this.onArrowLeftKey(e,!0);break;case`Home`:this.onHomeKey(e,!0);break;case`End`:this.onEndKey(e,!0);break;case`Enter`:case`NumpadEnter`:this.onEnterKey(e);break;case`Escape`:this.onEscapeKey(e);break;case`Tab`:this.onTabKey(e,!0);break}},onFilterBlur:function(){this.focusedOptionIndex=-1},onFilterUpdated:function(){this.overlayVisible&&this.alignOverlay()},onOverlayClick:function(e){pe.emit(`overlay-click`,{originalEvent:e,target:this.$el})},onOverlayKeyDown:function(e){switch(e.code){case`Escape`:this.onEscapeKey(e);break}},onArrowDownKey:function(e){if(!this.overlayVisible)this.show();else{var t=this.focusedOptionIndex===-1?this.clicked?this.findFirstOptionIndex():this.findFirstFocusedOptionIndex():this.findNextOptionIndex(this.focusedOptionIndex);e.shiftKey&&this.onOptionSelectRange(e,this.startRangeIndex,t),this.changeFocusedOptionIndex(e,t)}e.preventDefault()},onArrowUpKey:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:!1;if(e.altKey&&!t)this.focusedOptionIndex!==-1&&this.onOptionSelect(e,this.visibleOptions[this.focusedOptionIndex]),this.overlayVisible&&this.hide(),e.preventDefault();else{var n=this.focusedOptionIndex===-1?this.clicked?this.findLastOptionIndex():this.findLastFocusedOptionIndex():this.findPrevOptionIndex(this.focusedOptionIndex);e.shiftKey&&this.onOptionSelectRange(e,n,this.startRangeIndex),this.changeFocusedOptionIndex(e,n),!this.overlayVisible&&this.show(),e.preventDefault()}},onArrowLeftKey:function(e){arguments.length>1&&arguments[1]!==void 0&&arguments[1]&&(this.focusedOptionIndex=-1)},onHomeKey:function(e){if(arguments.length>1&&arguments[1]!==void 0&&arguments[1]){var t=e.currentTarget;e.shiftKey?t.setSelectionRange(0,e.target.selectionStart):(t.setSelectionRange(0,0),this.focusedOptionIndex=-1)}else{var n=e.metaKey||e.ctrlKey,r=this.findFirstOptionIndex();e.shiftKey&&n&&this.onOptionSelectRange(e,r,this.startRangeIndex),this.changeFocusedOptionIndex(e,r),!this.overlayVisible&&this.show()}e.preventDefault()},onEndKey:function(e){if(arguments.length>1&&arguments[1]!==void 0&&arguments[1]){var t=e.currentTarget;if(e.shiftKey)t.setSelectionRange(e.target.selectionStart,t.value.length);else{var n=t.value.length;t.setSelectionRange(n,n),this.focusedOptionIndex=-1}}else{var r=e.metaKey||e.ctrlKey,i=this.findLastOptionIndex();e.shiftKey&&r&&this.onOptionSelectRange(e,this.startRangeIndex,i),this.changeFocusedOptionIndex(e,i),!this.overlayVisible&&this.show()}e.preventDefault()},onPageUpKey:function(e){this.scrollInView(0),e.preventDefault()},onPageDownKey:function(e){this.scrollInView(this.visibleOptions.length-1),e.preventDefault()},onEnterKey:function(e){this.overlayVisible?this.focusedOptionIndex!==-1&&(e.shiftKey?this.onOptionSelectRange(e,this.focusedOptionIndex):this.onOptionSelect(e,this.visibleOptions[this.focusedOptionIndex])):(this.focusedOptionIndex=-1,this.onArrowDownKey(e)),e.preventDefault()},onEscapeKey:function(e){this.overlayVisible&&(this.hide(!0),e.stopPropagation()),e.preventDefault()},onTabKey:function(e){arguments.length>1&&arguments[1]!==void 0&&arguments[1]||(this.overlayVisible&&this.hasFocusableElements()?(g(e.shiftKey?this.$refs.lastHiddenFocusableElementOnOverlay:this.$refs.firstHiddenFocusableElementOnOverlay),e.preventDefault()):(this.focusedOptionIndex!==-1&&this.onOptionSelect(e,this.visibleOptions[this.focusedOptionIndex]),this.overlayVisible&&this.hide(this.filter)))},onShiftKey:function(){this.startRangeIndex=this.focusedOptionIndex},onOverlayEnter:function(e){N.set(`overlay`,e,this.$primevue.config.zIndex.overlay),ne(e,{position:`absolute`,top:`0`}),this.alignOverlay(),this.scrollInView(),this.autoFilterFocus&&g(this.$refs.filterInput.$el),this.autoUpdateModel(),this.$attrSelector&&e.setAttribute(this.$attrSelector,``)},onOverlayAfterEnter:function(){this.bindOutsideClickListener(),this.bindScrollListener(),this.bindResizeListener(),this.$emit(`show`)},onOverlayLeave:function(e){e.style.pointerEvents=`none`,this.unbindOutsideClickListener(),this.unbindScrollListener(),this.unbindResizeListener(),this.$emit(`hide`),this.overlay=null},onOverlayAfterLeave:function(e){N.clear(e)},alignOverlay:function(){this.appendTo===`self`?a(this.overlay,this.$el):(this.overlay.style.minWidth=e(this.$el)+`px`,r(this.overlay,this.$el))},bindOutsideClickListener:function(){var e=this;this.outsideClickListener||(this.outsideClickListener=function(t){e.overlayVisible&&e.isOutsideClicked(t)&&e.hide()},document.addEventListener(`click`,this.outsideClickListener,!0))},unbindOutsideClickListener:function(){this.outsideClickListener&&=(document.removeEventListener(`click`,this.outsideClickListener,!0),null)},bindScrollListener:function(){var e=this;this.scrollHandler||=new fe(this.$refs.container,function(){e.overlayVisible&&e.hide()}),this.scrollHandler.bindScrollListener()},unbindScrollListener:function(){this.scrollHandler&&this.scrollHandler.unbindScrollListener()},bindResizeListener:function(){var e=this;this.resizeListener||(this.resizeListener=function(){e.overlayVisible&&!te()&&e.hide()},window.addEventListener(`resize`,this.resizeListener))},unbindResizeListener:function(){this.resizeListener&&=(window.removeEventListener(`resize`,this.resizeListener),null)},isOutsideClicked:function(e){return!(this.$el.isSameNode(e.target)||this.$el.contains(e.target)||this.overlay&&this.overlay.contains(e.target))},getLabelByValue:function(e){var t=this,n=(this.optionGroupLabel?this.flatOptions(this.options):this.options||[]).find(function(n){return!t.isOptionGroup(n)&&h(t.getOptionValue(n),e,t.equalityKey)});return this.getOptionLabel(n)},getSelectedItemsLabel:function(){var e=/{(.*?)}/,t=this.selectedItemsLabel||this.$primevue.config.locale.selectionMessage;return e.test(t)?t.replace(t.match(e)[0],this.d_value.length+``):t},onToggleAll:function(e){var t=this;if(this.selectAll!==null)this.$emit(`selectall-change`,{originalEvent:e,checked:!this.allSelected});else{var n=this.allSelected?[]:this.visibleOptions.filter(function(e){return t.isValidOption(e)}).map(function(e){return t.getOptionValue(e)});this.updateModel(e,n)}},removeOption:function(e,t){var n=this;e.stopPropagation();var r=this.d_value.filter(function(e){return!h(e,t,n.equalityKey)});this.updateModel(e,r)},clearFilter:function(){this.filterValue=null},hasFocusableElements:function(){return m(this.overlay,`:not([data-p-hidden-focusable="true"])`).length>0},isOptionMatched:function(e){return this.isValidOption(e)&&typeof this.getOptionLabel(e)==`string`&&this.getOptionLabel(e)?.toLocaleLowerCase(this.filterLocale).startsWith(this.searchValue.toLocaleLowerCase(this.filterLocale))},isValidOption:function(e){return i(e)&&!(this.isOptionDisabled(e)||this.isOptionGroup(e))},isValidSelectedOption:function(e){return this.isValidOption(e)&&this.isSelected(e)},isEquals:function(e,t){return h(e,t,this.equalityKey)},isSelected:function(e){var t=this,n=this.getOptionValue(e);return(this.d_value||[]).some(function(e){return t.isEquals(e,n)})},findFirstOptionIndex:function(){var e=this;return this.visibleOptions.findIndex(function(t){return e.isValidOption(t)})},findLastOptionIndex:function(){var e=this;return t(this.visibleOptions,function(t){return e.isValidOption(t)})},findNextOptionIndex:function(e){var t=this,n=e<this.visibleOptions.length-1?this.visibleOptions.slice(e+1).findIndex(function(e){return t.isValidOption(e)}):-1;return n>-1?n+e+1:e},findPrevOptionIndex:function(e){var n=this,r=e>0?t(this.visibleOptions.slice(0,e),function(e){return n.isValidOption(e)}):-1;return r>-1?r:e},findSelectedOptionIndex:function(){var e=this;if(this.$filled){for(var t=function(){var t=e.d_value[r],n=e.visibleOptions.findIndex(function(n){return e.isValidSelectedOption(n)&&e.isEquals(t,e.getOptionValue(n))});if(n>-1)return{v:n}},n,r=this.d_value.length-1;r>=0;r--)if(n=t(),n)return n.v}return-1},findFirstSelectedOptionIndex:function(){var e=this;return this.$filled?this.visibleOptions.findIndex(function(t){return e.isValidSelectedOption(t)}):-1},findLastSelectedOptionIndex:function(){var e=this;return this.$filled?t(this.visibleOptions,function(t){return e.isValidSelectedOption(t)}):-1},findNextSelectedOptionIndex:function(e){var t=this,n=this.$filled&&e<this.visibleOptions.length-1?this.visibleOptions.slice(e+1).findIndex(function(e){return t.isValidSelectedOption(e)}):-1;return n>-1?n+e+1:-1},findPrevSelectedOptionIndex:function(e){var n=this,r=this.$filled&&e>0?t(this.visibleOptions.slice(0,e),function(e){return n.isValidSelectedOption(e)}):-1;return r>-1?r:-1},findNearestSelectedOptionIndex:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:!1,n=-1;return this.$filled&&(t?(n=this.findPrevSelectedOptionIndex(e),n=n===-1?this.findNextSelectedOptionIndex(e):n):(n=this.findNextSelectedOptionIndex(e),n=n===-1?this.findPrevSelectedOptionIndex(e):n)),n>-1?n:e},findFirstFocusedOptionIndex:function(){var e=this.findFirstSelectedOptionIndex();return e<0?this.findFirstOptionIndex():e},findLastFocusedOptionIndex:function(){var e=this.findSelectedOptionIndex();return e<0?this.findLastOptionIndex():e},searchOptions:function(e){var t=this;this.searchValue=(this.searchValue||``)+e.key;var n=-1;i(this.searchValue)&&(this.focusedOptionIndex===-1?n=this.visibleOptions.findIndex(function(e){return t.isOptionMatched(e)}):(n=this.visibleOptions.slice(this.focusedOptionIndex).findIndex(function(e){return t.isOptionMatched(e)}),n=n===-1?this.visibleOptions.slice(0,this.focusedOptionIndex).findIndex(function(e){return t.isOptionMatched(e)}):n+this.focusedOptionIndex),n===-1&&this.focusedOptionIndex===-1&&(n=this.findFirstFocusedOptionIndex()),n!==-1&&this.changeFocusedOptionIndex(e,n)),this.searchTimeout&&clearTimeout(this.searchTimeout),this.searchTimeout=setTimeout(function(){t.searchValue=``,t.searchTimeout=null},500)},changeFocusedOptionIndex:function(e,t){this.focusedOptionIndex!==t&&(this.focusedOptionIndex=t,this.scrollInView(),this.selectOnFocus&&this.onOptionSelect(e,this.visibleOptions[t]))},scrollInView:function(){var e=this,t=arguments.length>0&&arguments[0]!==void 0?arguments[0]:-1;this.$nextTick(function(){var n=t===-1?e.focusedOptionId:`${e.$id}_${t}`,r=l(e.list,`li[id="${n}"]`);r?r.scrollIntoView&&r.scrollIntoView({block:`nearest`,inline:`nearest`}):e.virtualScrollerDisabled||e.virtualScroller&&e.virtualScroller.scrollToIndex(t===-1?e.focusedOptionIndex:t)})},autoUpdateModel:function(){if(this.autoOptionFocus&&(this.focusedOptionIndex=this.findFirstFocusedOptionIndex()),this.selectOnFocus&&this.autoOptionFocus&&!this.$filled){var e=this.getOptionValue(this.visibleOptions[this.focusedOptionIndex]);this.updateModel(null,[e])}},updateModel:function(e,t){this.writeValue(t,e),this.$emit(`change`,{originalEvent:e,value:t})},flatOptions:function(e){var t=this;return(e||[]).reduce(function(e,n,r){var i=t.getOptionGroupChildren(n);return i&&Array.isArray(i)?(e.push({optionGroup:n,group:!0,index:r}),i.forEach(function(t){return e.push(t)})):e.push(n),e},[])},overlayRef:function(e){this.overlay=e},listRef:function(e,t){this.list=e,t&&t(e)},virtualScrollerRef:function(e){this.virtualScroller=e}},computed:{visibleOptions:function(){var e=this,t=this.optionGroupLabel?this.flatOptions(this.options):this.options||[];if(this.filterValue){var n=B.filter(t,this.searchFields,this.filterValue,this.filterMatchMode,this.filterLocale);if(this.optionGroupLabel){var r=this.options||[],i=[];return r.forEach(function(t){var r=e.getOptionGroupChildren(t).filter(function(e){return n.includes(e)});r.length>0&&i.push(K(K({},t),{},q({},typeof e.optionGroupChildren==`string`?e.optionGroupChildren:`items`,J(r))))}),this.flatOptions(i)}return n}return t},label:function(){var e;if(this.d_value&&this.d_value.length)if(this.loading&&(!this.options||this.options.length===0))e=this.placeholder;else if(i(this.maxSelectedLabels)&&this.d_value.length>this.maxSelectedLabels)return this.getSelectedItemsLabel();else{e=``;for(var t=0;t<this.d_value.length;t++)t!==0&&(e+=`, `),e+=this.getLabelByValue(this.d_value[t])}else e=this.placeholder;return e},chipSelectedItems:function(){return i(this.maxSelectedLabels)&&this.d_value&&this.d_value.length>this.maxSelectedLabels},allSelected:function(){var e=this;return this.selectAll===null?i(this.visibleOptions)&&this.visibleOptions.every(function(t){return e.isOptionGroup(t)||e.isOptionDisabled(t)||e.isSelected(t)}):this.selectAll},hasSelectedOption:function(){return this.$filled},equalityKey:function(){return this.optionValue?null:this.dataKey},searchFields:function(){return this.filterFields||[this.optionLabel]},maxSelectionLimitReached:function(){return this.selectionLimit&&this.d_value&&this.d_value.length===this.selectionLimit},filterResultMessageText:function(){return i(this.visibleOptions)?this.filterMessageText.replaceAll(`{0}`,this.visibleOptions.length):this.emptyFilterMessageText},filterMessageText:function(){return this.filterMessage||this.$primevue.config.locale.searchMessage||``},emptyFilterMessageText:function(){return this.emptyFilterMessage||this.$primevue.config.locale.emptySearchMessage||this.$primevue.config.locale.emptyFilterMessage||``},emptyMessageText:function(){return this.emptyMessage||this.$primevue.config.locale.emptyMessage||``},selectionMessageText:function(){return this.selectionMessage||this.$primevue.config.locale.selectionMessage||``},emptySelectionMessageText:function(){return this.emptySelectionMessage||this.$primevue.config.locale.emptySelectionMessage||``},selectedMessageText:function(){return this.$filled?this.selectionMessageText.replaceAll(`{0}`,this.d_value.length):this.emptySelectionMessageText},focusedOptionId:function(){return this.focusedOptionIndex===-1?null:`${this.$id}_${this.focusedOptionIndex}`},ariaSetSize:function(){var e=this;return this.visibleOptions.filter(function(t){return!e.isOptionGroup(t)}).length},toggleAllAriaLabel:function(){return this.$primevue.config.locale.aria?this.$primevue.config.locale.aria[this.allSelected?`selectAll`:`unselectAll`]:void 0},listAriaLabel:function(){return this.$primevue.config.locale.aria?this.$primevue.config.locale.aria.listLabel:void 0},virtualScrollerDisabled:function(){return!this.virtualScrollerOptions},hasFluid:function(){return o(this.fluid)?!!this.$pcFluid:this.fluid},isClearIconVisible:function(){return this.showClear&&this.d_value&&this.d_value.length&&this.d_value!=null&&i(this.options)&&!this.disabled&&!this.loading},containerDataP:function(){return n(q({invalid:this.$invalid,disabled:this.disabled,focus:this.focused,fluid:this.$fluid,filled:this.$variant===`filled`},this.size,this.size))},labelDataP:function(){return n(q(q(q({placeholder:this.label===this.placeholder,clearable:this.showClear,disabled:this.disabled},this.size,this.size),`has-chip`,this.display===`chip`&&this.d_value&&this.d_value.length&&(this.maxSelectedLabels?this.d_value.length<=this.maxSelectedLabels:!0)),`empty`,!this.placeholder&&!this.$filled))},dropdownIconDataP:function(){return n(q({},this.size,this.size))},overlayDataP:function(){return n(q({},`portal-`+this.appendTo,`portal-`+this.appendTo))}},directives:{ripple:d},components:{InputText:ue,Checkbox:H,VirtualScroller:L,Portal:de,Chip:U,IconField:I,InputIcon:z,TimesIcon:V,SearchIcon:P,ChevronDownIcon:R,SpinnerIcon:ee,CheckIcon:F}};function Z(e){"@babel/helpers - typeof";return Z=typeof Symbol==`function`&&typeof Symbol.iterator==`symbol`?function(e){return typeof e}:function(e){return e&&typeof Symbol==`function`&&e.constructor===Symbol&&e!==Symbol.prototype?`symbol`:typeof e},Z(e)}function Q(e,t,n){return(t=De(t))in e?Object.defineProperty(e,t,{value:n,enumerable:!0,configurable:!0,writable:!0}):e[t]=n,e}function De(e){var t=Oe(e,`string`);return Z(t)==`symbol`?t:t+``}function Oe(e,t){if(Z(e)!=`object`||!e)return e;var n=e[Symbol.toPrimitive];if(n!==void 0){var r=n.call(e,t);if(Z(r)!=`object`)return r;throw TypeError(`@@toPrimitive must return a primitive value.`)}return(t===`string`?String:Number)(e)}var ke=[`data-p`],Ae=[`id`,`disabled`,`placeholder`,`tabindex`,`aria-label`,`aria-labelledby`,`aria-expanded`,`aria-controls`,`aria-activedescendant`,`aria-invalid`],$=[`data-p`],je={key:1},Me=[`data-p`],Ne=[`id`,`aria-label`],Pe=[`id`],Fe=[`id`,`aria-label`,`aria-selected`,`aria-disabled`,`aria-setsize`,`aria-posinset`,`onClick`,`onMousemove`,`data-p-selected`,`data-p-focused`,`data-p-disabled`];function Ie(e,t,n,r,i,a){var o=j(`Chip`),s=j(`SpinnerIcon`),c=j(`Checkbox`),l=j(`InputText`),u=j(`SearchIcon`),d=j(`InputIcon`),f=j(`IconField`),p=j(`VirtualScroller`),m=j(`Portal`),h=ie(`ripple`);return x(),T(`div`,v({ref:`container`,class:e.cx(`root`),style:e.sx(`root`),onClick:t[7]||=function(){return a.onContainerClick&&a.onContainerClick.apply(a,arguments)},"data-p":a.containerDataP},e.ptmi(`root`)),[O(`div`,v({class:`p-hidden-accessible`},e.ptm(`hiddenInputContainer`),{"data-p-hidden-accessible":!0}),[O(`input`,v({ref:`focusInput`,id:e.inputId,type:`text`,readonly:``,disabled:e.disabled,placeholder:e.placeholder,tabindex:e.disabled?-1:e.tabindex,role:`combobox`,"aria-label":e.ariaLabel,"aria-labelledby":e.ariaLabelledby,"aria-haspopup":`listbox`,"aria-expanded":i.overlayVisible,"aria-controls":i.overlayVisible?e.$id+`_list`:void 0,"aria-activedescendant":i.focused?a.focusedOptionId:void 0,"aria-invalid":e.invalid||void 0,onFocus:t[0]||=function(){return a.onFocus&&a.onFocus.apply(a,arguments)},onBlur:t[1]||=function(){return a.onBlur&&a.onBlur.apply(a,arguments)},onKeydown:t[2]||=function(){return a.onKeyDown&&a.onKeyDown.apply(a,arguments)}},e.ptm(`hiddenInput`)),null,16,Ae)],16),O(`div`,v({class:e.cx(`labelContainer`)},e.ptm(`labelContainer`)),[O(`div`,v({class:e.cx(`label`),"data-p":a.labelDataP},e.ptm(`label`)),[S(e.$slots,`value`,{value:e.d_value,placeholder:e.placeholder},function(){return[e.display===`comma`?(x(),T(k,{key:0},[D(M(a.label||`empty`),1)],64)):e.display===`chip`?(x(),T(k,{key:1},[e.loading&&(!e.options||e.options.length===0)?(x(),T(k,{key:0},[D(M(e.placeholder||`empty`),1)],64)):a.chipSelectedItems?(x(),T(`span`,je,M(a.label),1)):(x(!0),T(k,{key:2},b(e.d_value,function(t,n){return x(),T(`span`,v({key:`chip-${a.getLabelByValue(t)}_${n}`,class:e.cx(`chipItem`)},{ref_for:!0},e.ptm(`chipItem`)),[S(e.$slots,`chip`,{value:t,removeCallback:function(e){return a.removeOption(e,t)}},function(){return[E(o,{class:y(e.cx(`pcChip`)),label:a.getLabelByValue(t),removeIcon:e.chipIcon||e.removeTokenIcon,removable:``,unstyled:e.unstyled,onRemove:function(e){return a.removeOption(e,t)},pt:e.ptm(`pcChip`)},{removeicon:_(function(){return[S(e.$slots,e.$slots.chipicon?`chipicon`:`removetokenicon`,{class:y(e.cx(`chipIcon`)),item:t,removeCallback:function(e){return a.removeOption(e,t)}})]}),_:2},1032,[`class`,`label`,`removeIcon`,`unstyled`,`onRemove`,`pt`])]})],16)}),128)),!e.d_value||e.d_value.length===0?(x(),T(k,{key:3},[D(M(e.placeholder||`empty`),1)],64)):w(``,!0)],64)):w(``,!0)]})],16,$)],16),a.isClearIconVisible?S(e.$slots,`clearicon`,{key:0,class:y(e.cx(`clearIcon`)),clearCallback:a.onClearClick},function(){return[(x(),A(C(e.clearIcon?`i`:`TimesIcon`),v({ref:`clearIcon`,class:[e.cx(`clearIcon`),e.clearIcon],onClick:a.onClearClick},e.ptm(`clearIcon`),{"data-pc-section":`clearicon`}),null,16,[`class`,`onClick`]))]}):w(``,!0),O(`div`,v({class:e.cx(`dropdown`)},e.ptm(`dropdown`)),[e.loading?S(e.$slots,`loadingicon`,{key:0,class:y(e.cx(`loadingIcon`))},function(){return[e.loadingIcon?(x(),T(`span`,v({key:0,class:[e.cx(`loadingIcon`),`pi-spin`,e.loadingIcon],"aria-hidden":`true`},e.ptm(`loadingIcon`)),null,16)):(x(),A(s,v({key:1,class:e.cx(`loadingIcon`),spin:``,"aria-hidden":`true`},e.ptm(`loadingIcon`)),null,16,[`class`]))]}):S(e.$slots,`dropdownicon`,{key:1,class:y(e.cx(`dropdownIcon`))},function(){return[(x(),A(C(e.dropdownIcon?`span`:`ChevronDownIcon`),v({class:[e.cx(`dropdownIcon`),e.dropdownIcon],"aria-hidden":`true`,"data-p":a.dropdownIconDataP},e.ptm(`dropdownIcon`)),null,16,[`class`,`data-p`]))]})],16),E(m,{appendTo:e.appendTo},{default:_(function(){return[E(ce,v({name:`p-anchored-overlay`,onEnter:a.onOverlayEnter,onAfterEnter:a.onOverlayAfterEnter,onLeave:a.onOverlayLeave,onAfterLeave:a.onOverlayAfterLeave},e.ptm(`transition`)),{default:_(function(){return[i.overlayVisible?(x(),T(`div`,v({key:0,ref:a.overlayRef,style:[e.panelStyle,e.overlayStyle],class:[e.cx(`overlay`),e.panelClass,e.overlayClass],onClick:t[5]||=function(){return a.onOverlayClick&&a.onOverlayClick.apply(a,arguments)},onKeydown:t[6]||=function(){return a.onOverlayKeyDown&&a.onOverlayKeyDown.apply(a,arguments)},"data-p":a.overlayDataP},e.ptm(`overlay`)),[O(`span`,v({ref:`firstHiddenFocusableElementOnOverlay`,role:`presentation`,"aria-hidden":`true`,class:`p-hidden-accessible p-hidden-focusable`,tabindex:0,onFocus:t[3]||=function(){return a.onFirstHiddenFocus&&a.onFirstHiddenFocus.apply(a,arguments)}},e.ptm(`hiddenFirstFocusableEl`),{"data-p-hidden-accessible":!0,"data-p-hidden-focusable":!0}),null,16),S(e.$slots,`header`,{value:e.d_value,options:a.visibleOptions}),e.showToggleAll&&e.selectionLimit==null||e.filter?(x(),T(`div`,v({key:0,class:e.cx(`header`)},e.ptm(`header`)),[e.showToggleAll&&e.selectionLimit==null?(x(),A(c,{key:0,modelValue:a.allSelected,binary:!0,disabled:e.disabled,variant:e.variant,"aria-label":a.toggleAllAriaLabel,onChange:a.onToggleAll,unstyled:e.unstyled,pt:a.getHeaderCheckboxPTOptions(`pcHeaderCheckbox`),formControl:{novalidate:!0}},{icon:_(function(t){return[e.$slots.headercheckboxicon?(x(),A(C(e.$slots.headercheckboxicon),{key:0,checked:t.checked,class:y(t.class)},null,8,[`checked`,`class`])):t.checked?(x(),A(C(e.checkboxIcon?`span`:`CheckIcon`),v({key:1,class:[t.class,Q({},e.checkboxIcon,t.checked)]},a.getHeaderCheckboxPTOptions(`pcHeaderCheckbox.icon`)),null,16,[`class`])):w(``,!0)]}),_:1},8,[`modelValue`,`disabled`,`variant`,`aria-label`,`onChange`,`unstyled`,`pt`])):w(``,!0),e.filter?(x(),A(f,{key:1,class:y(e.cx(`pcFilterContainer`)),unstyled:e.unstyled,pt:e.ptm(`pcFilterContainer`)},{default:_(function(){return[E(l,{ref:`filterInput`,value:i.filterValue,onVnodeMounted:a.onFilterUpdated,onVnodeUpdated:a.onFilterUpdated,class:y(e.cx(`pcFilter`)),placeholder:e.filterPlaceholder,disabled:e.disabled,variant:e.variant,unstyled:e.unstyled,role:`searchbox`,autocomplete:`off`,"aria-owns":e.$id+`_list`,"aria-activedescendant":a.focusedOptionId,onKeydown:a.onFilterKeyDown,onBlur:a.onFilterBlur,onInput:a.onFilterChange,pt:e.ptm(`pcFilter`),formControl:{novalidate:!0}},null,8,[`value`,`onVnodeMounted`,`onVnodeUpdated`,`class`,`placeholder`,`disabled`,`variant`,`unstyled`,`aria-owns`,`aria-activedescendant`,`onKeydown`,`onBlur`,`onInput`,`pt`]),E(d,{unstyled:e.unstyled,pt:e.ptm(`pcFilterIconContainer`)},{default:_(function(){return[S(e.$slots,`filtericon`,{},function(){return[e.filterIcon?(x(),T(`span`,v({key:0,class:e.filterIcon},e.ptm(`filterIcon`)),null,16)):(x(),A(u,ae(v({key:1},e.ptm(`filterIcon`))),null,16))]})]}),_:3},8,[`unstyled`,`pt`])]}),_:3},8,[`class`,`unstyled`,`pt`])):w(``,!0),e.filter?(x(),T(`span`,v({key:2,role:`status`,"aria-live":`polite`,class:`p-hidden-accessible`},e.ptm(`hiddenFilterResult`),{"data-p-hidden-accessible":!0}),M(a.filterResultMessageText),17)):w(``,!0)],16)):w(``,!0),O(`div`,v({class:e.cx(`listContainer`),style:{"max-height":a.virtualScrollerDisabled?e.scrollHeight:``}},e.ptm(`listContainer`)),[E(p,v({ref:a.virtualScrollerRef},e.virtualScrollerOptions,{items:a.visibleOptions,style:{height:e.scrollHeight},tabindex:-1,disabled:a.virtualScrollerDisabled,pt:e.ptm(`virtualScroller`)}),se({content:_(function(t){var n=t.styleClass,r=t.contentRef,o=t.items,s=t.getItemOptions,l=t.contentStyle,u=t.itemSize;return[O(`ul`,v({ref:function(e){return a.listRef(e,r)},id:e.$id+`_list`,class:[e.cx(`list`),n],style:l,role:`listbox`,"aria-multiselectable":`true`,"aria-label":a.listAriaLabel},e.ptm(`list`)),[(x(!0),T(k,null,b(o,function(t,n){return x(),T(k,{key:a.getOptionRenderKey(t,a.getOptionIndex(n,s))},[a.isOptionGroup(t)?(x(),T(`li`,v({key:0,id:e.$id+`_`+a.getOptionIndex(n,s),style:{height:u?u+`px`:void 0},class:e.cx(`optionGroup`),role:`option`},{ref_for:!0},e.ptm(`optionGroup`)),[S(e.$slots,`optiongroup`,{option:t.optionGroup,index:a.getOptionIndex(n,s)},function(){return[D(M(a.getOptionGroupLabel(t.optionGroup)),1)]})],16,Pe)):oe((x(),T(`li`,v({key:1,id:e.$id+`_`+a.getOptionIndex(n,s),style:{height:u?u+`px`:void 0},class:e.cx(`option`,{option:t,index:n,getItemOptions:s}),role:`option`,"aria-label":a.getOptionLabel(t),"aria-selected":a.isSelected(t),"aria-disabled":a.isOptionDisabled(t),"aria-setsize":a.ariaSetSize,"aria-posinset":a.getAriaPosInset(a.getOptionIndex(n,s)),onClick:function(e){return a.onOptionSelect(e,t,a.getOptionIndex(n,s),!0)},onMousemove:function(e){return a.onOptionMouseMove(e,a.getOptionIndex(n,s))}},{ref_for:!0},a.getCheckboxPTOptions(t,s,n,`option`),{"data-p-selected":a.isSelected(t),"data-p-focused":i.focusedOptionIndex===a.getOptionIndex(n,s),"data-p-disabled":a.isOptionDisabled(t)}),[E(c,{defaultValue:a.isSelected(t),binary:!0,tabindex:-1,variant:e.variant,unstyled:e.unstyled,pt:a.getCheckboxPTOptions(t,s,n,`pcOptionCheckbox`),formControl:{novalidate:!0}},{icon:_(function(r){return[e.$slots.optioncheckboxicon||e.$slots.itemcheckboxicon?(x(),A(C(e.$slots.optioncheckboxicon||e.$slots.itemcheckboxicon),{key:0,checked:r.checked,class:y(r.class)},null,8,[`checked`,`class`])):r.checked?(x(),A(C(e.checkboxIcon?`span`:`CheckIcon`),v({key:1,class:[r.class,Q({},e.checkboxIcon,r.checked)]},{ref_for:!0},a.getCheckboxPTOptions(t,s,n,`pcOptionCheckbox.icon`)),null,16,[`class`])):w(``,!0)]}),_:2},1032,[`defaultValue`,`variant`,`unstyled`,`pt`]),S(e.$slots,`option`,{option:t,selected:a.isSelected(t),index:a.getOptionIndex(n,s)},function(){return[O(`span`,v({ref_for:!0},e.ptm(`optionLabel`)),M(a.getOptionLabel(t)),17)]})],16,Fe)),[[h]])],64)}),128)),i.filterValue&&(!o||o&&o.length===0)?(x(),T(`li`,v({key:0,class:e.cx(`emptyMessage`),role:`option`},e.ptm(`emptyMessage`)),[S(e.$slots,`emptyfilter`,{},function(){return[D(M(a.emptyFilterMessageText),1)]})],16)):!e.options||e.options&&e.options.length===0?(x(),T(`li`,v({key:1,class:e.cx(`emptyMessage`),role:`option`},e.ptm(`emptyMessage`)),[S(e.$slots,`empty`,{},function(){return[D(M(a.emptyMessageText),1)]})],16)):w(``,!0)],16,Ne)]}),_:2},[e.$slots.loader?{name:`loader`,fn:_(function(t){var n=t.options;return[S(e.$slots,`loader`,{options:n})]}),key:`0`}:void 0]),1040,[`items`,`style`,`disabled`,`pt`])],16),S(e.$slots,`footer`,{value:e.d_value,options:a.visibleOptions}),!e.options||e.options&&e.options.length===0?(x(),T(`span`,v({key:1,role:`status`,"aria-live":`polite`,class:`p-hidden-accessible`},e.ptm(`hiddenEmptyMessage`),{"data-p-hidden-accessible":!0}),M(a.emptyMessageText),17)):w(``,!0),O(`span`,v({role:`status`,"aria-live":`polite`,class:`p-hidden-accessible`},e.ptm(`hiddenSelectedMessage`),{"data-p-hidden-accessible":!0}),M(a.selectedMessageText),17),O(`span`,v({ref:`lastHiddenFocusableElementOnOverlay`,role:`presentation`,"aria-hidden":`true`,class:`p-hidden-accessible p-hidden-focusable`,tabindex:0,onFocus:t[4]||=function(){return a.onLastHiddenFocus&&a.onLastHiddenFocus.apply(a,arguments)}},e.ptm(`hiddenLastFocusableEl`),{"data-p-hidden-accessible":!0,"data-p-hidden-focusable":!0}),null,16)],16,Me)):w(``,!0)]}),_:3},16,[`onEnter`,`onAfterEnter`,`onLeave`,`onAfterLeave`])]}),_:3},8,[`appendTo`])],16,ke)}X.render=Ie;export{X as t};
//# sourceMappingURL=multiselect-C6j-yErs.js.map