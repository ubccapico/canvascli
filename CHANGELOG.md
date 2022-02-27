# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Version number is based on [Semver](https://semver.org/).
Note that major version zero (0.y.z) is for initial development and anything may change at any time.

## [Unreleased]

### Added
- Show mean and median grade in plot
- Add selection to show raw percentage in the plot

### Fixed
- Make final notes easier to read

## [0.3.3] - 2021-11-12

### Added
- Warn when there are unposted canvas assignment

### Fixed
- Remove suffix number in session since this is not used in the FSC.
- Change to a more suitable number of histogram bins.

## [0.3.2] - 2021-07-07

### Added
- Support for the Canvas override final grade column.

## [0.3.1] - 2021-06-01

### Added
- canvascli is now on PyPI!
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
