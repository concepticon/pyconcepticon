# Changes


## [4.1.0] - 2026-10-28

We do not upload sources to CDSTAR anymore. Note that this is a breaking change in the sense that
`pyconcepticon` will not work as before with `concepticon-data` versions up to 3.4.0. While some
sort of backwards compatibility could have been preserved by optionally reading a `cdstar.json`
catalog listing sources, we decided against doing this because it will be of limited value once
the CDSTAR service is not available anymore.


## [4.0.0] - 2026-05-16

Major upgrade of all dependencies.