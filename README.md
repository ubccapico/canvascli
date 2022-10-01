# canvascli

`canvascli` downloads grades from Canvas,
converts them into the format required
for final submission to the FSC at UBC,
and creates a few helpful visualizations.

## Installation

`canvascli` requires a recent version of Python and its package manager `pip`.
After installing those ([e.g. via miniconda](https://docs.conda.io/en/latest/miniconda.html)),
you can run this command from your terminal.

```shell
python -m pip install -U canvascli
```

## Usage

All `canvascli` functionality requires that you have [created an Canvas API access
token](https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-manage-API-access-tokens-as-an-instructor/ta-p/1177),
so do that first if you don't have one already.

> When running `canvascli`,
you can either paste your Canvas token when prompted at the command line
(ideally using a password manager, e.g. [KeePassXC](https://keepassxc.org/)),
or [store it in an environment variable](https://www.poftut.com/how-to-set-environment-variables-for-linux-windows-bsd-and-macosx/) named `CANVAS_PAT`.

Typing `canvascli` at the command prompt will show the general help message
including the available sub-commands.
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
and creates a few helpful visualizations of the final grades
and assignment scores.
Run `canvascli prepare-fsc-grades --help`
to view all available options.

If you don't know the Canvas course id of your course,
`canvascli` can check for you:

```shell
canvascli show-courses
```

This will output a table with all the courses
your API token has access to.
Run `canvascli show-courses --help`
to view all available options.

<details><summary>

## Shell completion (optional, click to expand)

</summary>

If you want suggestions for subcommands and option flags when you press <kbd>TAB</kbd>
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

</details>

## Questions and contributing

Questions and contributions are welcome!
The best way to get in touch is to
[open a new issue or discussion](https://github.com/joelostblom/canvascli/issues/new/choose).
Remember to follow the [Code of Conduct](CODE_OF_CONDUCT.md)
when you participate in this project.
