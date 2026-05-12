import{d as e,f as t}from"./useToast-O7zy2Fch.js";import{E as n,P as r,R as i,d as a,f as o,l as s}from"./runtime-core.esm-bundler-bePl7dj1.js";var c={name:`Card`,extends:{name:`BaseCard`,extends:e,style:t.extend({name:`card`,style:`
    .p-card {
        background: dt('card.background');
        color: dt('card.color');
        box-shadow: dt('card.shadow');
        border-radius: dt('card.border.radius');
        display: flex;
        flex-direction: column;
    }

    .p-card-caption {
        display: flex;
        flex-direction: column;
        gap: dt('card.caption.gap');
    }

    .p-card-body {
        padding: dt('card.body.padding');
        display: flex;
        flex-direction: column;
        gap: dt('card.body.gap');
    }

    .p-card-title {
        font-size: dt('card.title.font.size');
        font-weight: dt('card.title.font.weight');
    }

    .p-card-subtitle {
        color: dt('card.subtitle.color');
    }
`,classes:{root:`p-card p-component`,header:`p-card-header`,body:`p-card-body`,caption:`p-card-caption`,title:`p-card-title`,subtitle:`p-card-subtitle`,content:`p-card-content`,footer:`p-card-footer`}}),provide:function(){return{$pcCard:this,$parentInstance:this}}},inheritAttrs:!1};function l(e,t,c,l,u,d){return r(),o(`div`,n({class:e.cx(`root`)},e.ptmi(`root`)),[e.$slots.header?(r(),o(`div`,n({key:0,class:e.cx(`header`)},e.ptm(`header`)),[i(e.$slots,`header`)],16)):a(``,!0),s(`div`,n({class:e.cx(`body`)},e.ptm(`body`)),[e.$slots.title||e.$slots.subtitle?(r(),o(`div`,n({key:0,class:e.cx(`caption`)},e.ptm(`caption`)),[e.$slots.title?(r(),o(`div`,n({key:0,class:e.cx(`title`)},e.ptm(`title`)),[i(e.$slots,`title`)],16)):a(``,!0),e.$slots.subtitle?(r(),o(`div`,n({key:1,class:e.cx(`subtitle`)},e.ptm(`subtitle`)),[i(e.$slots,`subtitle`)],16)):a(``,!0)],16)):a(``,!0),s(`div`,n({class:e.cx(`content`)},e.ptm(`content`)),[i(e.$slots,`content`)],16),e.$slots.footer?(r(),o(`div`,n({key:1,class:e.cx(`footer`)},e.ptm(`footer`)),[i(e.$slots,`footer`)],16)):a(``,!0)],16)],16)}c.render=l;export{c as t};
//# sourceMappingURL=card-CNSwn7AS.js.map