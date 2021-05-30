# canvascli

`canvascli` downloads grades from Canvas
and converts them into the format required
for final submission to the FSC at UBC.

## Installation

`canvascli` can be installed via `pip install canvascli`.

## Usage

All `canvascli` functionality requires that you have [created an Canvas API access
token](https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-manage-API-access-tokens-as-an-instructor/ta-p/1177),
so do that first if you don't have one already.
Typing `canvascli` at the command prompt will show the general help message
with the available sub-commands:

```text
Usage: canvascli [OPTIONS] COMMAND [ARGS]...

  A CLI to reformat and review Canvas grades.

  Examples:
      # Download grades from canvas and convert them to FSC format
      canvascli prepare-fsc-grades --course-id 53665

      # Show courses accessible by the given API token
      canvascli show-courses

  See the --help for each subcommand for more options.

  If you don't want to be prompted for your Canvas API token, you can save it
  to an environmental variable named CANVAS_PAT.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  prepare-fsc-grades       Prepare course grades for FSC submission.
  show-courses             Show courses accessible by the given API token.
```

The most common use case
is probably to prepare final grades for FSC submission,
which you can do like so:

```shell
canvascli prepare-fsc-grades --course-id 53665
```

This will save a CSV file in the current directory
which can be uploaded to the FSC.
This file should automatically be correctly formatted,
but it is a good idea to double check
in case there are unexpected changes
to how UBC inputs course info on Canvas.
`canvascli` drops students without a grade by default,
and creates a simple visualization of the grade distribution.
Run `canvascli prepare-fsc-grades --help`
to view all available options.

If you don't know the Canvas id of your course,
`canvascli` can check for you:

```shell
canvascli show-courses
```

This will output a table with all the courses
your API token has access to.
Run `canvascli show-courses --help`
to view all available options.

## Contributing

Contributions are welcome!
Please [read the guidelines](CONTRIBUTING.md).
