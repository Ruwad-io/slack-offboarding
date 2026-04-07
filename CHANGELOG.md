# [1.7.0](https://github.com/Ruwad-io/slack-offboarding/compare/v1.6.1...v1.7.0) (2026-04-07)


### Features

* readable group DM names and Sentry integration ([79f8907](https://github.com/Ruwad-io/slack-offboarding/commit/79f890746490818ab371aaf06fa078e36f850a3a))

## [1.6.1](https://github.com/Ruwad-io/slack-offboarding/compare/v1.6.0...v1.6.1) (2026-04-07)


### Bug Fixes

* generate PNG favicons, ICO, and apple-touch-icon from SVG ([fb6b192](https://github.com/Ruwad-io/slack-offboarding/commit/fb6b192385c1ffc60dac5dac4f134968ddcff24f))

# [1.6.0](https://github.com/Ruwad-io/slack-offboarding/compare/v1.5.2...v1.6.0) (2026-04-07)


### Bug Fixes

* use dynamic PORT for Railway deployment ([bdf05d3](https://github.com/Ruwad-io/slack-offboarding/commit/bdf05d36c056723b918c25bbfbb89e1101981952))


### Features

* add logo, favicon, SEO meta tags, sitemap and robots.txt ([db82c1c](https://github.com/Ruwad-io/slack-offboarding/commit/db82c1cb92813c56a28101e24e1a952f04af6af9))

## [1.5.2](https://github.com/Ruwad-io/slack-offboarding/compare/v1.5.1...v1.5.2) (2026-04-07)


### Bug Fixes

* Docker home dir for appuser, update test for nuke endpoint ([ac7e6d4](https://github.com/Ruwad-io/slack-offboarding/commit/ac7e6d4f2cfe36b865caa1f984e70549ec3b4dd4))

## [1.5.1](https://github.com/Ruwad-io/slack-offboarding/compare/v1.5.0...v1.5.1) (2026-04-07)


### Bug Fixes

* copy README.md in Docker deps stage for build ([f7dbf80](https://github.com/Ruwad-io/slack-offboarding/commit/f7dbf80b8f4ff4161481c13e63f1903a0d06a143))

# [1.5.0](https://github.com/Ruwad-io/slack-offboarding/compare/v1.4.1...v1.5.0) (2026-04-07)


### Features

* background job system with SSE for real-time progress ([94da48d](https://github.com/Ruwad-io/slack-offboarding/commit/94da48d20c7061f8a3809a86322c7a7ed52c93fa))

## [1.4.1](https://github.com/Ruwad-io/slack-offboarding/compare/v1.4.0...v1.4.1) (2026-04-07)


### Bug Fixes

* resolve lint errors — undefined variable, unused f-strings ([9bf19c9](https://github.com/Ruwad-io/slack-offboarding/commit/9bf19c98b3a49539dd9a8be2b2a5966f2405717b))

# [1.4.0](https://github.com/Ruwad-io/slack-offboarding/compare/v1.3.2...v1.4.0) (2026-04-07)


### Features

* adaptive concurrent deletion — starts fast, backs off on rate limits ([cd2d72c](https://github.com/Ruwad-io/slack-offboarding/commit/cd2d72cb02ae496dd4dc18684a0bc5d117bfa423))

## [1.3.2](https://github.com/Ruwad-io/slack-offboarding/compare/v1.3.1...v1.3.2) (2026-04-07)


### Bug Fixes

* show admin scope as optional in login instructions ([90f7b41](https://github.com/Ruwad-io/slack-offboarding/commit/90f7b41e0f682d26000ad63a873e26a4b3ff6618))

## [1.3.1](https://github.com/Ruwad-io/slack-offboarding/compare/v1.3.0...v1.3.1) (2026-04-07)


### Bug Fixes

* reduce delete delay from 1.2s to 0.5s for faster cleanup ([cf8dcb5](https://github.com/Ruwad-io/slack-offboarding/commit/cf8dcb5715df59a33c711679b6eb5768b90f0b53))

# [1.3.0](https://github.com/Ruwad-io/slack-offboarding/compare/v1.2.0...v1.3.0) (2026-04-07)


### Features

* auto-detect admin scope to delete others' messages in DMs ([e093ab0](https://github.com/Ruwad-io/slack-offboarding/commit/e093ab0c52bd4087524c6c7220580bac2997065b))

# [1.2.0](https://github.com/Ruwad-io/slack-offboarding/compare/v1.1.1...v1.2.0) (2026-04-07)


### Features

* full wipe — threads, group DMs, and channels support ([17b6237](https://github.com/Ruwad-io/slack-offboarding/commit/17b62379c84c2116aa263c620498fadbf2419e01))

## [1.1.1](https://github.com/Ruwad-io/slack-offboarding/compare/v1.1.0...v1.1.1) (2026-04-07)


### Bug Fixes

* reduce concurrency and add read delays to avoid rate limiting ([c627b7f](https://github.com/Ruwad-io/slack-offboarding/commit/c627b7f933d5fff2e496fa22f9a864513939019b))

# [1.1.0](https://github.com/Ruwad-io/slack-offboarding/compare/v1.0.2...v1.1.0) (2026-04-07)


### Features

* optimize API calls with bulk user fetch and concurrent counting ([7dc978b](https://github.com/Ruwad-io/slack-offboarding/commit/7dc978be39d8463f64f5a6e554683c4528a12bba))

## [1.0.2](https://github.com/Ruwad-io/slack-offboarding/compare/v1.0.1...v1.0.2) (2026-04-07)


### Bug Fixes

* add rate-limit retry and user cache to Slack API calls ([45d4283](https://github.com/Ruwad-io/slack-offboarding/commit/45d42832aec4c566c0d08b50d3d634258ae07787))

## [1.0.1](https://github.com/Ruwad-io/slack-offboarding/compare/v1.0.0...v1.0.1) (2026-04-07)


### Bug Fixes

* integrate PyPI publish into release workflow ([48b31d2](https://github.com/Ruwad-io/slack-offboarding/commit/48b31d25e45fe08cd13827cad36132f77cf49d2c))

# 1.0.0 (2026-04-07)


### Features

* add PyPI publishing with semantic-release CI/CD ([548c0ff](https://github.com/Ruwad-io/slack-offboarding/commit/548c0ffb4cf895e3bb611fcdc6bc74df64b141a8))
