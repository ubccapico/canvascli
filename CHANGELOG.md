# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Version number is based on [Semver](https://semver.org/).
Note that major version zero (0.y.z) is for initial development and anything may change at any time.

## [Unreleased]

### Added
- More readable visualizations

## [0.3.0] - 2021-05-31

### Added
- Round grades to integers.
- Cap grades at 100.
- Optional overrides of detected course info.

### Changed
- Abbreviate options flags.

## [0.2.1] - 2021-05-30

### Fixed
- Raise useful message upon unauthorized course access

## [0.2.0] - 2021-05-30

### Added
- `show_courses` got a `--filter` option to facilitate finding the right course.
- `canvascli` now has a `--version` flag.
- Shell completion.

### Changed
- The package was refactored to modularize functionality into subcommands, each with its own options.
- `dataclassy` is being used instead of `dataclasses` from `stdlib` in order to handle class inheritance with default values.

## [0.1.0] - 2021-05-28

Initial release.
