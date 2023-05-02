# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Version number is based on [Semver](https://semver.org/).
Note that major version zero (0.y.z) is for initial development and anything may change at any time.

## [0.6.0] 2023-05-02

### Added
- Automatically detect if there are multiple sections and display a boxplot for each section automatically.
- Include an option flag to include whether to group by section, grader, or nothing for the charts.
- Add search box to filter students names in the charts.
- Add percentile information to each student in the hover info in the scatter plot.
- Show progress bar while downloading grades
- Check for students being part of multiple sections.

### Changed
- Use boxplots with hover info (count, mean, median, quartiles) instead of just a marker for mean and median. Useful to report both overall stats and for each assignment/quiz.
- Extract student specific section ID instead of propagating the same ID to all students. Useful for courses with combined sections on Canvas.
- Lay out the scatterplot as a violin cloud so that it is easier to tell the shape of the distribution and the layout is deterministic when changing the dropdown menu or filtering via the search box.
- Prompt for inclusion of assignments and make the regex easier to use.
- Change the default number of histogram bins and the range to be more suitable for most grading scenarios.

### Fixed
- Adjust position of text and widgets to make the charts clearer.
- Support missing student numbers (happens with concluded courses).
- Support section IDs that are not numeric
- Align scales and ticks between boxplots and histograms.

## [0.5.1] 2022-10-01

### Changed
- Remove placeholder commands that have been implemented as part of viz already.

## [0.5.0] 2022-09-29

### Added
- Visualize individual student assignment scores.
    - This makes it possible to see how a student is doing over time
    and if intervention is needed.
- Optionally filter how many assignments show up in the visualization.
- Link Final Grade Plot with individual student assignment scores.
- Visualize score distributions for each assignment along with mean and median.
- Visualize a comparison between scores from each grader.
- Center chart titles and add more elaborate instructions.
- Show mean and median grade in plot.

### Changed
- Require Python 3.8 instead of 3.6 to ensure that importlib.metadata is in stdlib.
- Make saved messages stand out and simplify final info note.
- Make hover highlighting more intuitive and better explained.
- Filter out unpublished assignment and those missing a max score.
- Put assignment titles on top of plots instead of to the left.
- Maintain assignment order from Canvas in all visualizations.
- Only show a sample of the students with unposted assignments.

### Fixed
- Make rounding work with dfs containing None instead of NaN
  (happens when all values are None for an assignment and there is no type casting)

## [0.4.0] - 2022-04-30

### Added
- Show mean and median grade in plot.
- Add selection to show raw percentage in the plot.
- Visualize unposted student grades.
- Improve warning message for students with an unposted grade
  that would change their final grade.
- Allow filtering courses by date
  and only show last year's courses by default.
- Print version number and check for the latest version online.

### Changed
- The grade drop threshold now applies to the unposted score.
  rather than the posted score.
- Make output notes and warnings stand out more.

### Fixed
- Make end note easier to read.
- Provide a default value instead of crashing when a course is missing a name.

## [0.3.3] - 2021-11-12

### Added
- Warn when there are unposted canvas assignment.

### Fixed
- Remove suffix number in session since this is not used in the FSC.
- Change to a more suitable number of histogram bins.

## [0.3.2] - 2021-07-07

### Added
- Support for the Canvas override final grade column.

## [0.3.1] - 2021-06-01

### Added
- canvascli is now on PyPI!
- More readable visualizations.

## [0.3.0] - 2021-05-31

### Added
- Round grades to integers.
- Cap grades at 100.
- Optional overrides of detected course info.

### Changed
- Abbreviate options flags.

## [0.2.1] - 2021-05-30

### Fixed
- Raise useful message upon unauthorized course access.

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
