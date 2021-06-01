# canvascli

`canvascli` downloads grades from Canvas
and converts them into the format required
for final submission to the FSC at UBC.

## Installation

`canvascli` requires a recent version of Python and its package manager `pip`.
After installing those ([e.g. via miniconda](https://docs.conda.io/en/latest/miniconda.html)),
you can run this command from your terminal.

```shell
pip install canvascli
```

## Usage

All `canvascli` functionality requires that you have [created an Canvas API access
token](https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-manage-API-access-tokens-as-an-instructor/ta-p/1177),
so do that first if you don't have one already.
Typing `canvascli` at the command prompt will show the general help message
including the available sub-commands.

<!--
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
-->

The most common use case
is probably to prepare final grades for FSC submission,
which you can do like so:

```shell
canvascli prepare-fsc-grades --course-id 53665
```

This will save a CSV file in the current directory
which can be uploaded to the FSC.
The file should automatically be correctly formatted,
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

> If you don't want to be prompted for your Canvas API token each time,
you can save it to an environmental variable named CANVAS_PAT
(if you are using GitBash's default terminal on Windows,
you will not be able to paste into the `canvascli` prompt
and defining the environmental variable is required).

## Shell completion

If you want subcommands and options to complete when you press <kbd>TAB</kbd>
you can download the corresponding completion file
from the GitHub repository
and source it in your terminal's configuration file.
If you don't want to do this manually,
you can run one of the following commands
(don't forget to restart your shell afterwards).

### Zsh

> First make sure that your zsh general shell completion enabled
by adding `autoload -Uz compinit && compinit` to your `.zshrc`;
it is important that this line is added before running the command below.

```sh
curl -Ss https://raw.githubusercontent.com/joelostblom/canvascli/main/canvascli-complete.zsh > ~/.canvascli-complete.zsh && echo ". ~/.canvascli-complete.zsh" >> ~/.zshrc
```

### Bash

> Bash shell completion requires bash >= 4.0
(notably macOS ships with 3.x so use zsh instead).
If you are using GitBash for Windows,
change `.bashrc` to `.bash_profile` in the command below,
and note that you will only get shell completion after typing `cavascli`,
not `canvascli.exe`.

```sh
curl -Ss https://raw.githubusercontent.com/joelostblom/canvascli/main/canvascli-complete.bash > ~/.canvascli-complete.bash && echo ". ~/.canvascli-complete.bash" >> ~/.bashrc
```

## Questions and contributing

Questions and contributions are welcome!
The best way to get in touch is to
[open a new issue or discussion](https://github.com/joelostblom/canvascli/issues/new/choose).
Remember to follow the [Code of Conduct](CODE_OF_CONDUCT.md)
when you participate in this project.
