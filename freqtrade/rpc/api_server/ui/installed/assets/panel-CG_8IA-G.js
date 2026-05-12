import{Et as e,a as t,d as n,f as r,i}from"./useToast-O7zy2Fch.js";import{$ as a,E as o,Ft as s,P as c,R as l,V as u,d,et as f,f as p,g as m,l as h,u as g,z as _,zt as v}from"./runtime-core.esm-bundler-bePl7dj1.js";import{i as y,l as b}from"./inputtext-BBrbwrLU.js";import{n as x}from"./checkbox-DY17IWXO.js";import{t as S}from"./plus-BlFz_eaQ.js";var C=r.extend({name:`panel`,style:`
    .p-panel {
        display: block;
        border: 1px solid dt('panel.border.color');
        border-radius: dt('panel.border.radius');
        background: dt('panel.background');
        color: dt('panel.color');
    }

    .p-panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: dt('panel.header.padding');
        background: dt('panel.header.background');
        color: dt('panel.header.color');
        border-style: solid;
        border-width: dt('panel.header.border.width');
        border-color: dt('panel.header.border.color');
        border-radius: dt('panel.header.border.radius');
    }

    .p-panel-toggleable .p-panel-header {
        padding: dt('panel.toggleable.header.padding');
    }

    .p-panel-title {
        line-height: 1;
        font-weight: dt('panel.title.font.weight');
    }

    .p-panel-content-container {
        display: grid;
        grid-template-rows: 1fr;
    }

    .p-panel-content-wrapper {
        min-height: 0;
    }

    .p-panel-content {
        padding: dt('panel.content.padding');
    }

    .p-panel-footer {
        padding: dt('panel.footer.padding');
    }
`,classes:{root:function(e){return[`p-panel p-component`,{"p-panel-toggleable":e.props.toggleable}]},header:`p-panel-header`,title:`p-panel-title`,headerActions:`p-panel-header-actions`,pcToggleButton:`p-panel-toggle-button`,contentContainer:`p-panel-content-container`,contentWrapper:`p-panel-content-wrapper`,content:`p-panel-content`,footer:`p-panel-footer`}}),w={name:`Panel`,extends:{name:`BasePanel`,extends:n,props:{header:String,toggleable:Boolean,collapsed:Boolean,toggleButtonProps:{type:Object,default:function(){return{severity:`secondary`,text:!0,rounded:!0}}}},style:C,provide:function(){return{$pcPanel:this,$parentInstance:this}}},inheritAttrs:!1,emits:[`update:collapsed`,`toggle`],data:function(){return{d_collapsed:this.collapsed}},watch:{collapsed:function(e){this.d_collapsed=e}},methods:{toggle:function(e){this.d_collapsed=!this.d_collapsed,this.$emit(`update:collapsed`,this.d_collapsed),this.$emit(`toggle`,{originalEvent:e,value:this.d_collapsed})},onKeyDown:function(e){(e.code===`Enter`||e.code===`NumpadEnter`||e.code===`Space`)&&(this.toggle(e),e.preventDefault())}},computed:{buttonAriaLabel:function(){return this.toggleButtonProps&&this.toggleButtonProps.ariaLabel?this.toggleButtonProps.ariaLabel:this.header},dataP:function(){return e({toggleable:this.toggleable})}},components:{PlusIcon:S,MinusIcon:x,Button:i},directives:{ripple:t}},T=[`data-p`],E=[`data-p`],D=[`id`],O=[`id`,`aria-labelledby`];function k(e,t,n,r,i,x){var S=_(`Button`);return c(),p(`div`,o({class:e.cx(`root`),"data-p":x.dataP},e.ptmi(`root`)),[h(`div`,o({class:e.cx(`header`),"data-p":x.dataP},e.ptm(`header`)),[l(e.$slots,`header`,{id:e.$id+`_header`,class:s(e.cx(`title`)),collapsed:i.d_collapsed},function(){return[e.header?(c(),p(`span`,o({key:0,id:e.$id+`_header`,class:e.cx(`title`)},e.ptm(`title`)),v(e.header),17,D)):d(``,!0)]}),h(`div`,o({class:e.cx(`headerActions`)},e.ptm(`headerActions`)),[l(e.$slots,`icons`),e.toggleable?l(e.$slots,`togglebutton`,{key:0,collapsed:i.d_collapsed,toggleCallback:function(e){return x.toggle(e)},keydownCallback:function(e){return x.onKeyDown(e)}},function(){return[m(S,o({id:e.$id+`_header`,class:e.cx(`pcToggleButton`),"aria-label":x.buttonAriaLabel,"aria-controls":e.$id+`_content`,"aria-expanded":!i.d_collapsed,unstyled:e.unstyled,onClick:t[0]||=function(e){return x.toggle(e)},onKeydown:t[1]||=function(e){return x.onKeyDown(e)}},e.toggleButtonProps,{pt:e.ptm(`pcToggleButton`)}),{icon:a(function(t){return[l(e.$slots,e.$slots.toggleicon?`toggleicon`:`togglericon`,{collapsed:i.d_collapsed},function(){return[(c(),g(u(i.d_collapsed?`PlusIcon`:`MinusIcon`),o({class:t.class},e.ptm(`pcToggleButton`).icon),null,16,[`class`]))]})]}),_:3},16,[`id`,`class`,`aria-label`,`aria-controls`,`aria-expanded`,`unstyled`,`pt`])]}):d(``,!0)],16)],16,E),m(y,o({name:`p-collapsible`},e.ptm(`transition`)),{default:a(function(){return[f(h(`div`,o({id:e.$id+`_content`,class:e.cx(`contentContainer`),role:`region`,"aria-labelledby":e.$id+`_header`},e.ptm(`contentContainer`)),[h(`div`,o({class:e.cx(`contentWrapper`)},e.ptm(`contentWrapper`)),[h(`div`,o({class:e.cx(`content`)},e.ptm(`content`)),[l(e.$slots,`default`)],16),e.$slots.footer?(c(),p(`div`,o({key:0,class:e.cx(`footer`)},e.ptm(`footer`)),[l(e.$slots,`footer`)],16)):d(``,!0)],16)],16,O),[[b,!i.d_collapsed]])]}),_:3},16)],16,T)}w.render=k;export{w as t};
//# sourceMappingURL=panel-CG_8IA-G.js.map