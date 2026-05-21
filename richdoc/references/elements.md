# richdoc — element attribute reference

Auto-derived from `richdoc components`. For the most current detail, run that command directly. Tags are listed in schema order.

## `<rd-page>`
- **Optional:** `theme`, `mode`, `width`, `toc`, `prefs`, `diagram-endpoint`
- **Children:** any (plain HTML or rd-* allowed)
- `theme` enum: `editorial-warm`, `graphite-modern`
- `mode` enum: `light`, `dark`, `auto`
- `width` enum: `narrow`, `standard`, `wide`, `full`
- `toc` enum: `auto`, `right`, `left`, `top`
- `prefs` enum: `off`

## `<rd-hero>`
- **Required:** `title`
- **Optional:** `eyebrow`, `lede`, `meta`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-banner>`
- **Required:** `type`
- **Optional:** `message`
- **Children:** any (plain HTML or rd-* allowed)
- `type` enum: `draft`, `frozen`, `archived`, `confidential`, `info`

## `<rd-section>`
- **Optional:** `title`, `id`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-cols>`
- **Optional:** `n`, `template`
- **Children:** any (plain HTML or rd-* allowed)
- `n` enum: `2`, `3`, `4`

## `<rd-card>`
- **Optional:** `title`, `accent`
- **Children:** any (plain HTML or rd-* allowed)
- `accent` enum: `info`, `success`, `warn`, `danger`, `muted`

## `<rd-callout>`
- **Required:** `type`
- **Optional:** `title`
- **Children:** any (plain HTML or rd-* allowed)
- `type` enum: `info`, `success`, `warn`, `danger`, `note`, `tldr`

## `<rd-kv>`
- **Optional:** `title`, `layout`
- **Children (rd-*):** `<rd-row>`
- `layout` enum: `inline`, `stacked`

## `<rd-row>`
- **Required:** `key`
- **Parents:** `<rd-kv>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-badge>`
- **Optional:** `variant`
- **Children:** any (plain HTML or rd-* allowed)
- `variant` enum: `info`, `success`, `warn`, `danger`, `muted`

## `<rd-stat>`
- **Required:** `value`
- **Optional:** `label`, `trend`, `delta`, `tone`
- `trend` enum: `up`, `down`, `flat`
- `tone` enum: `positive`, `negative`, `neutral`

## `<rd-progress>`
- **Required:** `value`
- **Optional:** `label`, `tone`
- `tone` enum: `positive`, `negative`, `neutral`

## `<rd-chart>`
- **Optional:** `variant`, `kind`, `data`, `format`, `x`, `y`, `series`, `labels`, `title`, `caption`, `height`, `width`, `legend`, `color`, `endpoint`
- `variant` enum: `chart`, `sparkline`
- `kind` enum: `bar`, `line`, `area`, `donut`, `scatter`, `heatmap`
- `format` enum: `json`, `csv`

## `<rd-update>`
- **Required:** `date`
- **Optional:** `author`, `kind`, `title`
- **Children:** any (plain HTML or rd-* allowed)
- `kind` enum: `release`, `change`, `note`

## `<rd-compare>`
- **Required:** `headers`
- **Children (rd-*):** `<rd-row-cells>`

## `<rd-row-cells>`
- **Required:** `label`
- **Parents:** `<rd-compare>`
- **Children (rd-*):** `<rd-cell>`

## `<rd-cell>`
- **Optional:** `tone`
- **Parents:** `<rd-row-cells>`
- **Children:** any (plain HTML or rd-* allowed)
- `tone` enum: `positive`, `negative`, `neutral`

## `<rd-rubric>`
- **Required:** `options`
- **Optional:** `scale`, `title`
- **Children (rd-*):** `<rd-criterion>`

## `<rd-criterion>`
- **Required:** `label`
- **Optional:** `weight`
- **Parents:** `<rd-rubric>`
- **Children (rd-*):** `<rd-score>`

## `<rd-score>`
- **Required:** `value`
- **Optional:** `note`
- **Parents:** `<rd-criterion>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-code>`
- **Optional:** `lang`, `title`, `line-numbers`, `highlight`, `start`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-diff>`
- **Optional:** `lang`, `title`, `line-numbers`

## `<rd-shell>`
- **Optional:** `title`
- **Children (rd-*):** `<rd-prompt>`, `<rd-output>`

## `<rd-prompt>`
- **Optional:** `cwd`, `user`
- **Parents:** `<rd-shell>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-output>`
- **Optional:** `tone`
- **Parents:** `<rd-shell>`
- **Children:** any (plain HTML or rd-* allowed)
- `tone` enum: `positive`, `negative`, `neutral`

## `<rd-math>`
- **Optional:** `display`
- `display` enum: `block`, `inline`

## `<rd-tabs>`
- **Children (rd-*):** `<rd-tab>`

## `<rd-tab>`
- **Required:** `label`
- **Optional:** `active`
- **Parents:** `<rd-tabs>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-timeline>`
- **Children (rd-*):** `<rd-event>`

## `<rd-event>`
- **Required:** `date`
- **Optional:** `title`
- **Parents:** `<rd-timeline>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-steps>`
- **Children (rd-*):** `<rd-step>`

## `<rd-step>`
- **Required:** `title`
- **Optional:** `done`
- **Parents:** `<rd-steps>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-detail>`
- **Required:** `summary`
- **Optional:** `variant`, `open`
- **Children:** any (plain HTML or rd-* allowed)
- `variant` enum: `panel`, `hairline`, `question`, `reveal`

## `<rd-checklist>`
- **Children (rd-*):** `<rd-task>`

## `<rd-task>`
- **Optional:** `done`, `assignee`, `due`
- **Parents:** `<rd-checklist>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-decision>`
- **Required:** `status`
- **Optional:** `id`, `date`, `deciders`, `title`
- **Children:** any (plain HTML or rd-* allowed)
- `status` enum: `proposed`, `accepted`, `superseded`, `rejected`

## `<rd-pros-cons>`
- **Optional:** `pros-title`, `cons-title`
- **Children (rd-*):** `<rd-pro>`, `<rd-con>`

## `<rd-pro>`
- **Parents:** `<rd-pros-cons>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-con>`
- **Parents:** `<rd-pros-cons>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-api>`
- **Required:** `method`, `path`
- **Optional:** `auth`, `title`
- **Children (rd-*):** `<rd-param>`, `<rd-response>`
- `method` enum: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`

## `<rd-param>`
- **Required:** `name`
- **Optional:** `in`, `required`, `type`, `default`
- **Parents:** `<rd-api>`
- **Children:** any (plain HTML or rd-* allowed)
- `in` enum: `query`, `path`, `body`, `header`

## `<rd-response>`
- **Required:** `status`
- **Optional:** `type`
- **Parents:** `<rd-api>`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-references>`
- **Optional:** `title`

## `<rd-ref>`
- **Required:** `key`
- **Optional:** `author`, `title`, `url`, `date`, `publisher`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-cite>`
- **Required:** `key`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-diagram>`
- **Required:** `lang`
- **Optional:** `endpoint`, `theme`, `title`, `caption`
- **Children:** any (plain HTML or rd-* allowed)
- `lang` enum: `mermaid`, `plantuml`, `graphviz`, `d2`, `dbml`, `bpmn`, `c4plantuml`, `erd`, `ditaa`, `excalidraw`, `nomnoml`, `pikchr`, `structurizr`, `svgbob`, `tikz`, `vega`, `vegalite`, `wavedrom`, `wireviz`, `bytefield`, `blockdiag`, `seqdiag`, `actdiag`, `nwdiag`, `packetdiag`, `rackdiag`

## `<rd-figure>`
- **Optional:** `caption`
- **Children:** any (plain HTML or rd-* allowed)

## `<rd-toc>`
- **Optional:** `levels`, `title`
- **Children (rd-*):** `<rd-chapter>`

## `<rd-chapter>`
- **Optional:** `href`
- **Parents:** `<rd-toc>`, `<rd-chapter>`
- **Children (rd-*):** `<rd-chapter>`

## `<rd-icon>`
- **Required:** `name`
- **Optional:** `size`, `label`
- `name` enum: 1960 values (run `richdoc components --tag rd-icon` for the full list)
- `size` enum: `sm`, `md`, `lg`

## `<rd-prefs>`
- **Children:** none
