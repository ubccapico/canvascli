"""A CLI to reformat and review Canvas grades.
See the README and class docstrings for more info.
"""
import getpass
import json
import os
import platform
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from importlib.metadata import version
from requests.exceptions import MissingSchema
from urllib.error import URLError

import altair as alt
import click
import numpy as np
import pandas as pd
from appdirs import user_data_dir
from canvasapi import Canvas
from canvasapi.exceptions import InvalidAccessToken, Unauthorized
from luddite import get_version_pypi
from pandas.io.formats import excel
from scipy import stats
from tqdm import tqdm
# Using https://github.com/biqqles/dataclassy instead of dataclasses from
# stdlibto allow for dataclass inheritance when there are default values. Could
# use a custom init but it gets messy and the advantage of using dataclasses is
# lost. Dataclass inheritance might be fixed in 3.10
# https://bugs.python.org/issue36077
from dataclassy import dataclass
from . import __version__


# Using this as a first try, might have to use an external file instead
alt.data_transformers.disable_max_rows()

@click.group()
@click.version_option(version=__version__, prog_name='canvascli')
def cli():
    """A CLI to reformat and review Canvas grades.

    \b
    Examples:
        # Download grades from canvas and convert them to their final submission format
        canvascli prepare-grades --course-id 53665
        \b
        # Show courses accessible by the given API token
        canvascli show-courses

    See the --help for each subcommand for more options.

    If you don't want to be prompted for your Canvas API token,
    you can save it to an environmental variable named CANVAS_PAT.
    """
    # Since canvascli might be useful for people who don't use Python
    # frequently, I have chosen to always print the program version and to
    # occasionally check for newer versions of canvascli online and to note if
    # one is found.
    canvascli_version = version('canvascli')
    click.echo(f'\ncanvascli version {canvascli_version}')

    if 'canvascli_prevent_update' in os.environ:
        pass
    else:
        data_dir = user_data_dir('canvascli')
        data_file = os.path.join(data_dir, 'data.json')
        try:
            # If the config file exists
            with open(data_file) as f:
                stored_data = json.load(f)
        except (FileNotFoundError, OSError, PermissionError):
            # Generate a default config when no file is found
            stored_data = {}
            stored_data['last_update_check'] = '2001-01-01'

        last_update_check = datetime.strptime(
            stored_data['last_update_check'],
            '%Y-%m-%d'
        )
        # Run a check online and update the config file if the last check was a long time ago
        if (datetime.now() - last_update_check) > pd.Timedelta(weeks=4):
            try:
                latest_version = get_version_pypi("canvascli")
                # Update `last_update_check` in the config if the update check is succesful
                if canvascli_version == latest_version:
                    os.makedirs(data_dir, exist_ok=True)
                    with open(data_file, 'w', encoding='utf-8') as f:
                        json.dump(
                            {'last_update_check': datetime.now().strftime('%Y-%m-%d')},
                            f,
                            ensure_ascii=False,
                            indent=4
                        )
                    # If no update was found, don't check again untill the env variables are cleared
                    # This avoids reading the settings file unnecessarily
                    # since the result will likely be the same in the same session anyways.
                    os.environ['canvascli_prevent_update'] = 'True'
                else:
                    click.secho('\nNOTE', fg='yellow', bold=True)
                    click.echo(
                        f'A new version ({latest_version}) is available'
                        '\nRead the release notes at https://github.com/joelostblom/canvascli/releases'
                        '\nand download it via `python -m pip install -U canvascli`.'
                    )
            except URLError:
                # If there is no connectivity
                pass
    return


@cli.command()
@click.option('--course-id', default=None, required=True, type=int, help='Canvas id'
              ' of the course to download grades from, e.g. 53665. This id'
              ' can be found by running `canvascli show-courses`'
              "(and in the course's canvas page URL). Default: None")
@click.option('--section', type=str, multiple=True, help='Which sections '
              ' to include in the exported spreadsheet. Common section IDs are 001, 002, etc.'
              ' The flag can be used multiple times to specify multiple sections.'
              ' Does not affect the visualizations. Default: All sections)')
@click.option('--filename', default=None, help='Name of the saved file and chart'
              ' (without file extension). Default: Automatic based on the course.')
@click.option('--api-url', default='https://canvas.ubc.ca', help='Base canvas URL.'
              ' Default: https://canvas.ubc.ca')
@click.option('--student-status', default='active', help='Which types of students'
              ' to download grades for. Default: active')
@click.option('--drop-students', default=None, help='Student numbers to drop,'
              ' in quotes separated by spaces, e.g. "14391238 30329123".'
              ' Useful for removing specific students. Default: None')
@click.option('--drop-threshold', default=0, help='Students with grades <='
              ' this threshold are dropped. Useful for removing test students'
              ' and students that dropped the course after completing some work.'
              ' Default: 0')
@click.option('--drop-na', default=True, help='Whether to drop students'
              ' that are missing info such as student number.'
              ' Useful for only removing test students. Default: True')
@click.option('--open-chart', default=None, type=bool, help='Whether to open'
              ' the grade distribution chart automatically.'
              ' Default: Ask unless specified')
@click.option('--filter-assignments', default=None, type=str, help='Regex to filter'
              ' which assignments are included in the assignment-specific visualizations'
              ' (case-sensitive). Does not affect the calculation or visualization'
              ' of the final grades. The special string "False" excludes all assignments. '
              'Default: Ask unless specified')
@click.option('--group-by', default=None, type=click.Choice(['Section', 'Grader']),
              help='Variable to group the visualizations by. A separate box plot'
              ' will be created for each group. Default: None (`Section` if there'
              ' are multiple sections, otherwise `Grader` if there are multiple graders,'
              ' otherwise nothing)')
@click.option('--override-campus', default=None, help='Override the automatically'
              ' detected course campus in the CSV file with this text. Default: None')
@click.option('--override-course', default=None, help='Override the automatically'
              ' detected course title in the CSV file with this text. Default: None')
@click.option('--override-section', default=None, help='Override the automatically'
              ' detected course section in the CSV file with this text. Default: None')
@click.option('--override-session', default=None, help='Override the automatically'
              ' detected course session in the CSV file with this text. Default: None')
@click.option('--override-subject', default=None, help='Override the automatically'
              ' detected course subject in the CSV file with this text. Default: None')
def prepare_grades(course_id, section, filename, api_url, student_status,
                   drop_students, drop_threshold, drop_na, open_chart,
                   filter_assignments, group_by, override_campus, override_course,
                   override_section, override_session, override_subject):
    """Prepare course grades for submission to e.g. Workday.
    \b
    Download grades from a canvas course and convert them to the format
    required for submission of final grades.

    Grades are rounded to whole percentages and capped at 100.
    Students with missing info or 0 grade are dropped by default.

    A CSV file is saved in the current directory,
    which can be uploaded directly to the file server, e.g. Workday.
    A grade distribution chart is saved in the current directory.

    \b
    Examples:
        # Download grades from canvas and convert them to their final submission format
        canvascli prepare_grades --course-id 53665
        \b
        # Give a custom file name and drop a specific student
        canvascli prepare_grades --course-id 53665 --drop-students "43659202"
    """
    prepared_grades = PreparedGrades(
        course_id, section, filename, api_url, student_status, drop_students,
        drop_threshold, drop_na, open_chart, filter_assignments, group_by, override_campus,
        override_course, override_section, override_session, override_subject)
    prepared_grades.connect_to_canvas()
    prepared_grades.connect_to_course()
    prepared_grades.get_canvas_grades()
    prepared_grades.drop_student_entries()
    prepared_grades.convert_grades_to_submission_format()
    if prepared_grades.prepared_grades.empty:
        click.echo('Did not find any assigned grades, exiting.')
    else:
        prepared_grades.save_prepared_grades_to_file()
        prepared_grades.plot_prepared_grade_distribution()
        prepared_grades.plot_assignment_scores()
        prepared_grades.layout_and_save_charts()
        prepared_grades.show_manual_grade_entry_note()
    return


@cli.command()
@click.option('--api-url', default='https://canvas.ubc.ca', help='Base canvas URL.'
              ' Default: https://canvas.ubc.ca')
@click.option('--filter', 'filter_', default='', help='Only show courses including'
              ' this string (case insensitve). Useful to narrow down the displayed'
              ' results. Default: "" (matches all courses)')
@click.option('--start-date', 'start_date_', default=None, help='Show courses'
              ' created at or after this date. Courses without a creation date are'
              ' always shown. Format "YYYY-MM-DD". Default: Show all courses'
              ' created within a year from today.')
def show_courses(api_url, filter_, start_date_):
    """Show courses accessible by the given API token.

    Examples:
        \b
        # Show all courses
        canvascli show-courses
        \b
        # Show only courses including the string "541"
        canvascli show-courses --filter 541
    """
    accessible_courses = AccessibleCourses(api_url, filter_, start_date_)
    accessible_courses.connect_to_canvas()
    accessible_courses.download_courses()
    accessible_courses.filter_and_show_courses()
    return


@dataclass
class CanvasConnection():
    """Parent class for initializing attributes shared between child classes."""
    invalid_canvas_url_msg: str = (
        '\nThe canvas URL you specified is invalid,'
        ' Please supply a URL in the folowing format: https://canvas.ubc.ca')
    invalid_canvas_api_token_msg: str = (
        '\nYour API token is invalid. The token you tried is:\n{}'
        '\n\nSee this canvas help page for how to setup up API tokens:'
        '\nhttps://community.canvaslms.com/t5/Instructor-Guide/How-do-I-manage-API-access-tokens-as-an-instructor/ta-p/1177')

    def connect_to_canvas(self):
        """Connect to a canvas instance."""
        click.echo('\nConnecting to canvas...')
        self.api_token = os.environ.get("CANVAS_PAT")
        if self.api_token is None:
            self.api_token = getpass.getpass(
                'Paste your canvas API token and press enter:')
        self.canvas = Canvas(self.api_url, self.api_token)
        return


@dataclass
class AccessibleCourses(CanvasConnection):
    """Show all courses accessible from a specific API token."""
    api_url: str
    filter_: str
    start_date_: str

    def download_courses(self):
        """Download all courses accessible from a specific API token."""
        self.courses = defaultdict(list)
        try:
            for course in self.canvas.get_courses():

                # Return a default value ('N/A') if the attribute is not found
                self.courses['id'].append(getattr(course, 'id', 'N/A'))
                self.courses['name'].append(getattr(course, 'name', 'N/A'))
                self.courses['end_at'].append(getattr(course, 'end_at', pd.NaT))
                self.courses['start_at'].append(getattr(course, 'start_at', pd.NaT))
                self.courses['created_at'].append(getattr(course, 'created_at', pd.NaT))
        # Show common exceptions in a way that is easy to understand
        except MissingSchema:
            raise SystemExit(self.invalid_canvas_url_msg)
        except InvalidAccessToken:
            raise SystemExit(self.invalid_canvas_api_token_msg.format(self.api_token))
        return

    def filter_and_show_courses(self):
        """Filter and show downloaded courses."""
        # The default is to include courses starting in the past year
        creation_date = pd.to_datetime(
            self.start_date_ or datetime.now() - pd.DateOffset(months=12),
            utc=True
        ).date()
        click.echo("Your API token has access to the following courses:\n")
        click.echo(
            pd.DataFrame(
                self.courses
            ).assign(
                created_at = lambda df: pd.to_datetime(df['created_at'], errors='coerce').dt.date
            ).query(
                'created_at > @creation_date | created_at.isna()'
            ).query(
                'name.str.contains(@self.filter_, case=False)',
                engine='python'
            ).sort_values(
                'created_at'
            ).drop(
                columns=['end_at', 'start_at']
            ).rename(
                columns={'id': 'ID', 'name': 'Name', 'created_at': 'Creation Date'}
            ).to_markdown(
                index=False
            )
        )
        return


@dataclass
class PreparedGrades(CanvasConnection):
    """Prepare grades for a specific course."""
    course_id: int
    section: str
    filename: str
    api_url: str
    student_status: str
    drop_students: str
    drop_threshold: int
    drop_na: bool
    open_chart: bool
    filter_assignments: str
    group_by: str
    override_campus: str
    override_course: str
    override_section: str
    override_session: str
    override_subject: str
    unauthorized_course_access_msg: str = (
        '\nYour API token is not authorized to access course {}.'
        '\nRun `canvascli show-courses` to see all courses you can access.')

    def connect_to_course(self):
        """Connect to as specific canvas course."""
        try:
            self.course = self.canvas.get_course(self.course_id)
        # Show common exceptions in a way that is easy to understand
        except MissingSchema:
            raise SystemExit(self.invalid_canvas_url_msg)
        except InvalidAccessToken:
            raise SystemExit(self.invalid_canvas_api_token_msg.format(self.api_token))
        except Unauthorized:
            raise SystemExit(self.unauthorized_course_access_msg.format(self.course_id))
        if self.filename is None:
            self.filename = (f'grades_{self.course.course_code.replace(" ", "-")}'
                             .replace('/', '-'))
        return

    def get_canvas_grades(self):
        """Download grades from a canvas course."""
        enrollments = self.course.get_enrollments(
            type=['StudentEnrollment'], state=[self.student_status]
        )
        canvas_grades = defaultdict(list)

        # This is shown in a later warning
        self.students_with_diff_between_current_and_final_grades = []
        # We can't know the length of `enrollments` since it is an iterable,
        # so this is the best progress bar we can get here
        enrollments_progress_bar = tqdm(
            enrollments,
            unit=' students',
            desc='Downloading student grades',
            bar_format='{desc}... {n}{unit}'
        )
        for enrollment in enrollments_progress_bar:
            canvas_grades['User ID'].append(enrollment.user['id'])

            # `sis_user_id` is removed from concluded courses by Canvas
            if 'sis_user_id' in enrollment.user:
                canvas_grades['Student Number'].append(enrollment.user['sis_user_id'])
            else:
                # A warning about this case is emitted further down
                canvas_grades['Student Number'].append('N/A')
            surname, preferred_name = enrollment.user['sortable_name'].split(', ')
            canvas_grades['Surname'].append(surname)
            canvas_grades['Preferred Name'].append(preferred_name)
            canvas_grades['Section'].append(enrollment.course_section_id)

            # Missing these two fields indicate a fatal permissions error
            if 'unposted_current_score' not in enrollment.grades or 'final_score' not in enrollment.grades:
                click.secho('\n\nERROR', fg='red', bold=True)
                click.echo(
                    'Cannot find the grading fields `unposted_current_score` and `final_score`.'
                    '\nThis usually mean that you do not have permission to read student grades.'
                    '\nContact LT hub to upgrade your role (to e.g. "instructor" or "course assistant").'
                    '\n\nThis is what you currently have permission to view:\n'
                )
                click.echo(enrollment.grades)
                raise SystemExit()

            # Unposted "current" is what matches what is seen on Canvas for a course in progress
            # Unposted "final" deducts points for assignments without a grade
            # (it treats them as if an explicit grade of `0` was given,
            # which is undesirable when checking students current progress in the course)
            canvas_grades['Unposted Percent Grade'].append(enrollment.grades['unposted_current_score'])

            # A warning message is later displayed for these students
            if 'override_score' in enrollment.grades:
                canvas_grades['Percent Grade'].append(enrollment.grades['override_score'])
                canvas_grades['override_final_score'].append(enrollment.grades['final_score'])
            else:
                canvas_grades['Percent Grade'].append(enrollment.grades['final_score'])
                canvas_grades['override_final_score'].append(0)

            # A warning message is later displayed for these students
            # Need to check for "final unposted" here rather than "current unposted"
            if 'unposted_final_score' in enrollment.grades:
                canvas_grades['Unposted Final Grade'].append(enrollment.grades['unposted_final_score'])
                if enrollment.grades['unposted_final_score'] != enrollment.grades['final_score']:
                    canvas_grades['different_unposted_score'].append(True)
                else:
                    canvas_grades['different_unposted_score'].append(False)
            else:
                canvas_grades['Unposted Final Grade'].append(pd.NA)
                canvas_grades['different_unposted_score'].append(False)

            # A warning message is later displayed for these students
            # This compares "current"/"total" (what is seen on canvas)
            # with "final" (what is exported).
            # The only field that is not explicitly checked is "unposted_current_score",
            # but that should not be needed as the general grade posting is already checked above
            if 'current_score' in enrollment.grades:
                canvas_grades['Current Grade'].append(enrollment.grades['current_score'])
                if enrollment.grades['current_score'] != enrollment.grades['final_score']:
                    canvas_grades['different_current_score'].append(True)
                else:
                    canvas_grades['different_current_score'].append(False)
            else:
                canvas_grades['Current Grade'].append(pd.NA)
                canvas_grades['different_current_score'].append(False)

        self.canvas_grades = pd.DataFrame(canvas_grades)

        # Warn about missing student numbers
        if (pd.DataFrame(canvas_grades)['Student Number'] == 'N/A').any():
            click.secho('\nWARNING', fg='red', bold=True)
            click.echo(
                'Could not find students numbers for at least one student.'
                '\nThis does not impact the visualizations,'
                '\nbut you must add student numbers manually'
                '\nbefore uploading the CSV file for submission.'
                '\nThis could happen because your course has concluded'
                '\nor because it includes a test student account.\n'
            )

        # Extract course section IDs for each students
        # We are relying on the same extraction pattern as for the prepared grades,
        # which LT hub mentioned should be safe to extract from the
        # canvas course code (for UBC courses in general).
        # There is no override for the individual student
        # which should be safe.
        # Originally there was a check to verify that the course section is a number
        # but it turns out some courses don't use numbers for the sections
        section_ids_and_names = {
            section.id: section.name.split()[2]
            for section in self.course.get_sections()
        }
        self.canvas_grades['Section'] = (
            self.canvas_grades['Section'].map(section_ids_and_names)
        )

        # Display a note that some student grades are manually overridden
        if self.canvas_grades['override_final_score'].sum() > 0:
            click.secho('\nNOTE', fg='yellow', bold=True)
            click.echo(
                'You have used the "Overide" column on Canvas'
                '\nto change the final score for the following students:\n'
            )
            click.echo(
                self.canvas_grades
                .query('override_final_score > 0')
                .rename(
                    columns={
                        'Percent Grade': 'Final Grade',
                        'Student Number': 'Student ID',
                        'override_final_score': 'Grade Before Override'
                    }
                )
                .assign(Name=lambda df: df['Preferred Name'] + ' ' + df['Surname'])
                [['Student ID', 'Name', 'Final Grade', 'Grade Before Override']]
                .to_markdown(index=False)
            )
            click.echo()
        self.canvas_grades = self.canvas_grades.drop(columns='override_final_score')

        # Warn about students with unposted grades that change their final scores
        different_unposted_score = self.canvas_grades.pop('different_unposted_score')
        # This is checked in the next condition but since that is an `elif` we need to pop here
        different_current_score = self.canvas_grades.pop('different_current_score')
        if different_unposted_score.sum() > 0:
            students_with_unposted_score = self.canvas_grades.query(
                '@different_unposted_score == True'
            )

            click.secho('\nWARNING', fg='red', bold=True)
            click.echo(
                'Remember to post all assignments on Canvas'
                '\nbefore creating the CSV-file to upload for submission.'
                '\nThere are currently unposted Canvas assignments'
                '\nthat would change the final score of '
                + click.style(f'{students_with_unposted_score.shape[0]} students.', bold=True)
            )
            if students_with_unposted_score.shape[0] > 5:
                click.echo('Showing the first five in the table below:\n')
            else:
                click.echo('Showing these students in the table below:\n')
            # Indexing up until the first 10 works even if there are fewer than 10 entries
            click.echo(
                students_with_unposted_score[:5]
                .rename(
                    columns={
                        'Percent Grade': 'Posted Grade',
                        'Unposted Final Grade': 'Unposted Grade',
                        'Student Number': 'Student ID',
                    }
                )
                .assign(Name=lambda df: df['Preferred Name'] + ' ' + df['Surname'])
                [['Student ID', 'Name', 'Posted Grade', 'Unposted Grade']]
                .to_markdown(index=False)
            )
            click.echo('')

        # Warn about having a different current score and final score
        # This can be true even if the above is not true,
        # e.g. from unpublished assignmend in weighted assignment groups
        # but not the other way around I think
        # We only show this warning if the other warning is not already shown,
        # so it doesn't get too noisy.
        # This should be safe since posting all grades is one of the conditions
        # that this warning relies on as well
        elif different_current_score.sum() > 0:
            students_with_diff_current_score = self.canvas_grades.query(
                '@different_current_score == True'
            )

            click.secho('\nWARNING', fg='red', bold=True)
            click.echo(
                'There are currently ungraded Canvas assignments'
                '\nthat would change the final score of '
                + click.style(f'{students_with_diff_current_score.shape[0]} students.', bold=True)
                + '\nGrade all assignments on Canvas before using canvascli' 
                '\nto create the CSV-file with final grades.'
                '\nNote that the "Total" grade shown on Canvas'
                '\nis not taking into account ungraded assignments (marked as "-"),'
                '\nso it is not the same as the final grade (which replaces "-" with "0").'
                '\nIf all such cases are for students who did not make a submission'
                '\nand therefore should get a 0, no action is required.'
                '\nIf a student should be excused from an assignment, enter "Ex" on Canvas'
                '\nto avoid counting the assignment towards their final grade.'
            )

            if students_with_diff_current_score.shape[0] > 5:
                click.echo('Showing the first five affected students in the table below:\n')
            else:
                click.echo('Showing the affected students in the table below:\n')
            # Indexing up until the first 10 works even if there are fewer than 10 entries
            click.echo(
                students_with_diff_current_score[:5]
                # Renaming the current grade to "total" to match the canvas interface
                # and make it easier to understand where this column is coming from
                .rename(
                    columns={
                        'Percent Grade': 'Final Grade',
                        'Current Grade': 'Canvas "Total"',
                        'Student Number': 'Student ID',
                    }
                )
                .assign(Name=lambda df: df['Preferred Name'] + ' ' + df['Surname'])
                [['Student ID', 'Name', 'Final Grade', 'Canvas "Total"']]
                .to_markdown(index=False)
            )
            click.echo('')

        # The unposted "final" grade is only needed for the comparison above
        # For everything else, we use the unposted "current" grade
        # since this allows to show the current progress in the course in the visualizations
        self.canvas_grades = self.canvas_grades.drop(columns='Unposted Final Grade')
        return

    def drop_student_entries(self):
        """Drop unwanted students entries such as test students and dropouts."""
        # Drop students under the grade thresholds
        # Test accounts and students who dropped the course often have a grade of zero
        dropped_students = self.canvas_grades.query(
            '`Unposted Percent Grade` <= @self.drop_threshold'
        )
        self.canvas_grades = self.canvas_grades.query(
            '`Unposted Percent Grade` > @self.drop_threshold'
        ).copy()

        # Drop students that have missing info in any field
        # These are also printed so that it is clear to the user what has happened
        # and they need to be explicit in disabling the behavior instead of
        # accidentally uploading empty fields when submitting final grades.
        if self.drop_na:
            dropped_students = pd.concat([
                dropped_students,
                self.canvas_grades[self.canvas_grades.isna().any(axis=1)]
                ],
                ignore_index=True
            )
            self.canvas_grades = self.canvas_grades.dropna()

        # Drop students explicitly
        if self.drop_students is not None:
            dropped_students = pd.concat([
                dropped_students,
                self.canvas_grades.query(
                    '`Student Number` in @self.drop_students.split()')
                ],
                ignore_index=True
            )
            self.canvas_grades = self.canvas_grades.query(
                '`Student Number` not in @self.drop_students.split()').copy()

        # Display the dropped students so the user can catch errors easily
        if dropped_students.shape[0] > 0:
            click.secho('\nNOTE', fg='yellow', bold=True)
            click.echo(
                f'Dropping {dropped_students.shape[0]}'
                f" {'students' if dropped_students.shape[0] > 1 else 'student'}"
                f' with missing information, a grade <= {self.drop_threshold},'
                '\nor that was explicitly dropped by student number:\n'
            )
            click.echo(
                dropped_students
                .rename(
                    columns={
                        'Percent Grade': 'Posted Grade',
                        'Unposted Percent Grade': 'Unposted Grade',
                        'Student Number': 'Student ID',
                    }
                )
                .assign(Name=lambda df: df['Preferred Name'] + ' ' + df['Surname'])
                [['Student ID', 'Name', 'Posted Grade', 'Unposted Grade']]
                .to_markdown(index=False)
            )
            click.echo()

        # It seems like students can be registered for multiple sections
        if self.canvas_grades.duplicated(subset='User ID').sum() > 0:
            click.secho('WARNING', fg='red', bold=True)
            click.echo(
                'The following students are enrolled in multiple sections.'
                '\nOnly the first occurrence will be kept.'
            )
            click.echo(
                self.canvas_grades[
                    self.canvas_grades['User ID']
                    .duplicated(keep=False)
                ]
                .drop(columns='Unposted Percent Grade')
                .to_markdown(index=False)
            )
            click.echo()
            self.canvas_grades = self.canvas_grades.drop_duplicates(subset='User ID')

        return

    def convert_grades_to_submission_format(self):
        """Convert grades to the final submission format."""
        self.campus = 'UBC'
        # LT hub mentioned that these fields should be safe to extract from the
        # canvas course code (for UBC courses in general), but there is an override
        # option just in case
        # Some course codes include multiple sessions in the name,
        # which is why we are doing this split in two steps and dropping everything
        # from index 2 to -2 since the session is already extracted for each student elsewhere
        subject_coursename_session = self.course.course_code.split()
        self.subject, self.course_name = subject_coursename_session[:2]
        self.session = subject_coursename_session[-1]

        if self.override_campus is not None:
            self.campus = self.override_campus
        if self.override_course is not None:
            self.course_name = self.override_course
        if self.override_section is not None:
            self.section = self.override_section
        if self.override_session is not None:
            self.session = self.override_session
        if self.override_subject is not None:
            self.subject = self.override_subject
        
        # Add required info to the dataframe; standing and standing reason are
        # blank by default and filled out manually when needed
        self.prepared_grades = self.canvas_grades.copy()
        additional_fields = [
            'Campus', 'Course', 'Session', 'Subject', 'Standing', 'Standing Reason'
        ]
        self.prepared_grades[additional_fields] = (
            self.campus, self.course_name, self.session, self.subject, '', '')
        
        self.prepared_grades['Grade Note'] = ''
        self.prepared_grades['Status'] = ''
        self.prepared_grades['Updated By'] = ''
        # Workday also does not adhere to the same format as Canvas for the Academic Period/Session because that would be too logical
        year = self.session[:4]
        term = self.session[4:]
        campus = f'UBC-{self.subject.split("_")[-1]}'
        self.prepared_grades['Academic Period'] = (
            f'{year} Summer Session ({campus})'
            if term == 'S1'
            else f'{year}-{int(year[2:]) + 1} Winter Term {term[1]} ({campus})'
        )

        # Round to whole percentage format since final submission requires it.
        # Using Decimal to always round up .5 instead of rounding to even,
        # which is the default in numpy but could seem unfair to individual students.
        # The Decimal type is not json serializable (issue for altair) so changing to int.
        self.prepared_grades['Exact Percent Grade'] = self.prepared_grades['Percent Grade']
        self.prepared_grades['Percent Grade'] = self.prepared_grades['Percent Grade'].apply(
            lambda x: Decimal(x).quantize(0, rounding=ROUND_HALF_UP)).astype(int)

        self.prepared_grades['Unposted Exact Percent Grade'] = self.prepared_grades['Unposted Percent Grade']
        self.prepared_grades['Unposted Percent Grade'] = self.prepared_grades['Unposted Percent Grade'].apply(
            lambda x: Decimal(x).quantize(0, rounding=ROUND_HALF_UP)).astype(int)

        # Cap grades at 100
        self.prepared_grades.loc[self.prepared_grades['Percent Grade'] > 100, 'Percent Grade'] = 100

        return

    def save_prepared_grades_to_file(self):
        """Write a CSV file that can be uploaded for final grade submission."""
        excel_file_name = self.filename + '.xlsx'
        # Note that Workday does not accept files created with openpyxl so we use xlsxwriter
        # which also has the advantage to be able to autofit the columns
        with pd.ExcelWriter(excel_file_name, engine='xlsxwriter') as writer: 
            # Workday has some issues with renderering default pandas header style
            excel.ExcelFormatter.header_style = None
            if not len(self.section):  # The default is an empty tuple which means "all sections"
                self.section = self.prepared_grades['Section'].unique()
            # Reorder columns to match the required Workday format
            self.prepared_grades.query(
                'Section in @self.section'
            ).rename(
                columns={
                    'Student Number': 'Student Id',
                    'Preferred Name': 'Student Preferred Name',
                    'Surname': 'Student Last Name',
                    'Percent Grade': 'Grade',
                    'Subject': 'Course Subject Code',
                    'Course': 'Course Number',
                    'Section': 'Section Number',
                }
            )[[
                'Student Id',
                'Student Preferred Name',
                'Student Last Name',
                'Grade',
                'Grade Note',
                'Academic Period',
                'Course Subject Code',
                'Course Number',
                'Section Number',
                'Status',
                'Updated By',
            ]].to_excel(
                writer,
                index=False,
                startrow=3,
                sheet_name='Sheet1'
            )
            writer.sheets['Sheet1'].autofit()
            # Redundant preamble that workday requires for no good reason
            writer.sheets['Sheet1'].write(0, 0, "Record Name:")
            writer.sheets['Sheet1'].write(0, 1, "Course Registrations")
            writer.sheets['Sheet1'].write(1, 0, "Exported On:")
            time_format = '%b %#d, %Y %#I:%#M %p' if platform.system() == 'Windows' else '%b %-d, %Y %-I:%-M %p'
            writer.sheets['Sheet1'].write(1, 1, pd.Timestamp.now().strftime(time_format))
        click.secho(f'Grades saved to {excel_file_name}.', bold=True, fg='green')
        return

    def plot_assignment_scores(self):
        # Prompt the user if they want to show assignments,
        # since it takes time to download them and makes the chart more noisy
        # Only show if `filter_assignments` is not already set to a string,
        # which indicates that the user already knows they want to include assignments
        if self.filter_assignments == 'False' or (
            not isinstance(self.filter_assignments, str)
            and not click.confirm('Download and plot assignment scores?', default=True)
        ):
            # Adding empty charts since there are concated charts later
            # that rely on the existence of these charts
            self.assignment_distributions = alt.Chart().mark_point(opacity=0)
            self.assignment_scores = alt.Chart().mark_point(opacity=0)
        else:
            # If we get here it means that the user has selected "Yes" in the prompt,
            # but not specified a string, so include all assignments
            if self.filter_assignments is None:
                self.filter_assignments = ''
            assignment_regex = re.compile(self.filter_assignments)
            assignments = [
                a for a in self.course.get_assignments()
                if (
                    a.published
                    and a.points_possible is not None
                    and a.points_possible > 0
                    and a.graded_submissions_exist
                    and assignment_regex.search(a.name)
                )
            ]

            # Raise error so that it is clear to the user what happens
            # when the regex does not match any assignments
            if not assignments:
                raise click.ClickException(
                    click.style(
                        'No assignment names matched the provided regular expression: '
                        f'"{self.filter_assignments}". Aborting...',
                        bold=True,
                        fg='red'
                    )
                )

            assignment_scores_dfs = []
            click.echo("Downloading assignment scores...")
            assignment_progress_bar = tqdm(assignments)
            for assignment in assignment_progress_bar:
                assignment_progress_bar.set_description(assignment.name)
                submissions = assignment.get_submissions()
                assignment_scores = defaultdict(list)
                for submission in submissions:
                    assignment_scores['User ID'].append(submission.user_id)
                    assignment_scores['Grader ID'].append(submission.grader_id)
                    assignment_scores['Score'].append(
                        100 * submission.score / assignment.points_possible
                        if submission.score is not None else None
                    )
                    assignment_scores['Assignment'].append(assignment.name)
                assignment_scores_dfs.append(pd.DataFrame(assignment_scores))
            # fillna required on pandas >=1.4.0 due to https://github.com/pandas-dev/pandas/issues/46922
            assignment_score_df = pd.concat(assignment_scores_dfs, ignore_index=True).fillna(np.nan)
            # Sometime a negative number is returned for the grader,
            # which does not make sense, maybe from gradescope?
            assignment_score_df.loc[assignment_score_df['Grader ID'] < 0, 'Grader ID']  = pd.NA
            user_ids_and_names = {
                user.id: [user.name, user.sis_user_id if hasattr(user, 'sis_user_id') else 'N/A']
                for user in self.course.get_users()
            }
            user_ids_and_names_df = pd.DataFrame.from_dict(
                user_ids_and_names, orient='index', columns=['Name', 'Student Number']
            )
            assignment_score_df['Grader'] = assignment_score_df['Grader ID'].map(
                user_ids_and_names_df['Name']
            )
            assignment_score_df['Name'] = assignment_score_df['User ID'].map(
                user_ids_and_names_df['Name']
            )
            assignment_score_df['Student Number'] = assignment_score_df['User ID'].map(
                user_ids_and_names_df['Student Number']
            )
            # The section number cannot be extracted via `get_users()`
            assignment_score_df['Section'] = (
                assignment_score_df['User ID'].map(
                    self.canvas_grades.set_index('User ID')['Section']
                )
            )

            # Using `round` instead of `Decimal` here
            # since the latter can't deal with a df with a single `None`
            # and because this is just to show on the assignment scores,
            # so it does not have to be fairly rounded like the final submission grades.
            assignment_score_df['Score'] = assignment_score_df['Score'].round(2)
            # self.canvas has had dropped students removed at this point
            # so we can use it to drop from the assignment score as well
            assignment_score_df = assignment_score_df.query(
                '`User ID` in @self.canvas_grades["User ID"]',
                engine='python'
            ).copy()

            # Plot scores for individual assignments
            # Start by figuring out how many groups there are to set chart height
            # and in what order to sort
            if self.group_by is None:
                if assignment_score_df['Section'].nunique() > 1:
                    self.group_by = 'Section'
                elif assignment_score_df['Grader'].nunique() > 1:
                    self.group_by = 'Grader'
            height = 80
            # If group_by is set either manually or automatically above
            if self.group_by is not None:
                if self.group_by == 'Section':
                    self.group_order = self.section_order
                elif self.group_by == 'Grader':
                    self.group_order = (
                        assignment_score_df
                        .groupby(self.group_by)
                        ['Score']
                        .median()
                        .sort_values()
                        .index.tolist()
                    )
                # Min height=80 for histograms to look nice
                # 20 is the default step size for categorical scale
                height = max(height, len(self.group_order) * 20)

            # assignment_order is only needed because VL does not support maintaining
            # the orignal order for facets https://github.com/vega/vega-lite/issues/6221
            assignment_order = assignment_score_df['Assignment'].unique().tolist()

            # Constant range 50 - 100 by default
            # Since this is also used for the scale/axis domain for the boxplots
            # we need to make sure that the boxplots and bins use the same min value;
            # a power of 5 works for this since the bin step is 5 so we floor the min value to the closest 5
            bin_extent = (
                min(
                    50,
                    (assignment_score_df['Score'].min() // 5) * 5
                ),
                100
            )

            boxplot_base = alt.Chart(
                assignment_score_df
            ).mark_boxplot(outliers={'opacity': 0}, median={'color': 'black'}).encode(
                alt.X('Score', scale=alt.Scale(zero=False)).scale(domain=bin_extent, nice=False),
                y=alt.value(height + 10),
            )
            boxplots = alt.layer(
                boxplot_base,
                boxplot_base.mark_point(size=30, shape='diamond', filled=True).encode(
                    alt.X('mean(Score)', scale=alt.Scale(zero=False)),
                    color=alt.value('#353535')
                ),
                boxplot_base.transform_aggregate(
                    min="min(Score)",
                    max="max(Score)",
                    mean="mean(Score)",
                    median="median(Score)",
                    q1="q1(Score)",
                    q3="q3(Score)",
                    count="count()",
                # Without setting the height here the tooltip region is too narrow,
                # and the height of the boxplot chart does not matter as it does for the overall grades boxplot,
                # not sure why it's different.
                ).mark_bar(opacity=0, height=20).encode(
                    x='q1:Q',
                    x2='q3:Q',
                    tooltip=alt.Tooltip(
                        ['min:Q', 'q1:Q', 'mean:Q', 'median:Q', 'q3:Q', 'max:Q', 'count:Q'],
                        format='.1f'
                    )
                )
            )

            histograms = alt.layer(
                alt.Chart(
                    assignment_score_df,
                    height=height,
                    width=355
                ).mark_bar().encode(
                    x=alt.X('Score', bin=alt.Bin(extent=bin_extent, step=2.5), axis=alt.Axis(offset=20)),
                    y=alt.Y('count()', title='Student Count'),
                ),
                boxplots,
            ).facet(
                title=alt.Title(
                    'Assignment Score Distributions',
                    subtitle=[
                        'Hover over the box to view exact summary statistics.',
                        'The "--filter-assignment" option controls what is shown here.'
                    ],
                    anchor='start',
                    dx=35,
                    dy=-5
                ),
                facet=alt.Facet('Assignment', title='', sort=assignment_order, header=alt.Header(labelPadding=0)),
                columns=1
            ).resolve_axis(
                x='independent'
            )

            if self.group_by is not None:
                boxplot_base = alt.Chart(
                    assignment_score_df.reset_index(),
                    height=height + 20,
                ).mark_boxplot(median={'color': 'black'}).encode(  # TODO increase thickness and switch from black in new altair version
                    alt.X('Score', scale=alt.Scale(zero=False, domain=bin_extent, nice=False)),
                    alt.Y(
                        f'{self.group_by}:N',
                        sort=self.group_order,
                        title='',
                        axis=alt.Axis(orient='right')
                    ),
                    alt.Color(
                        f'{self.group_by}:N',
                        sort=self.group_order[::-1],  # Reverse so that the highest value closest to the axis gets the most important color
                        legend=None,
                        scale=alt.Scale(range=self.colorscheme_groups)
                    )
                )
                boxplots = alt.layer(
                    boxplot_base,
                    boxplot_base.mark_point(size=30, shape='diamond', filled=True).encode(
                        alt.X('mean(Score)', scale=alt.Scale(zero=False)),
                        color=alt.value('#353535')
                    ),
                    boxplot_base.transform_aggregate(
                        min="min(Score)",
                        max="max(Score)",
                        mean="mean(Score)",
                        median="median(Score)",
                        q1="q1(Score)",
                        q3="q3(Score)",
                        count="count()",
                        groupby=[f'{self.group_by}']
                    ).mark_bar(opacity=0).encode(
                        x='q1:Q',
                        x2='q3:Q',
                        tooltip=alt.Tooltip(
                            ['min:Q', 'q1:Q', 'mean:Q', 'median:Q', 'q3:Q', 'max:Q', 'count:Q'],
                            format='.1f'
                        )
                    )
                ).facet(
                    title=alt.Title(
                        f'Comparison Between {self.group_by}s',
                        subtitle=[
                            'Hover over the box to view exact summary statistics.',
                            'The "--group-by" option controls what is shown here.'
                        ],
                        anchor='start',
                        dy=-5
                    ),
                    facet=alt.Facet('Assignment', title='', sort=assignment_order, header=alt.Header(labelPadding=0)),
                    columns=1
                ).resolve_scale(
                    y='independent' if self.group_by == 'Grader' else 'shared'
                ).resolve_axis(
                    x='independent'
                )

                self.assignment_distributions = alt.hconcat(
                    histograms,
                    boxplots,
                    spacing=100
                ).resolve_scale(
                    color='independent'  # Don't use the mean/median color range for the boxplot
                )
            else:
                self.assignment_distributions = histograms

            # Plot assignment scores
            assignment_score_df['Assignment scores stdev'] = assignment_score_df['User ID'].map(
                assignment_score_df.groupby('User ID')['Score'].std()
            )
            base = alt.Chart(
                assignment_score_df,
                title=alt.Title(
                    'Student Assignment Scores',
                    subtitle=[
                        'Hover near a point to highlight a line.',
                        'Hover directly over a point to view student info.',
                        'Click the "..." button to the right to save this page as PNG/SVG.',
                    ],
                    anchor='start',
                    dx=40
                ),
            ).mark_point(opacity=0).encode(
                y=alt.Y('Score', scale=alt.Scale(zero=False), title='Assignment Score (%)'),
                detail='User ID',
                x=alt.X('Assignment', title='', sort=assignment_order),
                # Having the tooltip here instead of in the transformed chart
                # makes it work with nearest,
                # but significantly slows down the higlighting of the line
                tooltip=['Name', 'Student Number', 'Score'],
            ).transform_filter(
                alt.expr.test(alt.expr.regexp(self.search_input, 'i'), alt.datum.Name)
            )
            width = min(1000, max(400, 80 * assignment_score_df['Assignment'].nunique()))
            self.assignment_scores = (
                base.add_params(
                    self.hover
                ) + base.mark_line(opacity=0.5, interpolate='monotone').encode(
                    color=alt.Color(
                        'Assignment scores stdev',
                        scale=alt.Scale(scheme='cividis', reverse=True),
                        title=['Stdev between', 'Assignments']
                    )
                ) + (base.mark_line(size=3, interpolate='monotone', color='maroon')
                + base.mark_circle(size=70, color='maroon', opacity=1).encode(
                    # tooltip=['Name', 'Student Number', 'Score'],
                    )
                ).transform_filter(
                    self.hover
                )).properties(
                    width=width,
                    height=280,
                ).interactive()
            return

    def plot_prepared_grade_distribution(self):

        def _compute_violin_cloud(series):
            """Create a violin-shaped point cloud.

            Compute the KDE and then place each point
            at a random position within the bounds of the KDE at that location.
            """

            # TODO include a scaling parameter so that few points renders a more compressed violin

            # The KDE needs at least 3 unique points to be computed
            if series.nunique() < 3:
                return pd.Series([0] * series.shape[0])
            # NAs are not supported in SciPy's density calculation
            na_series = series[series.isna()]
            no_na_series = series.dropna()
            no_na_sorted_series = no_na_series.sort_values()

            # Compute the density function of the data
            dens = stats.gaussian_kde(no_na_series)
            # Compute the density value for each data point
            pdf = dens(no_na_sorted_series)
            # Normalize the y-range so that the aces domain can be set predictably
            pdf = (pdf - pdf.min()) / (pdf.max() - pdf.min())

            # Randomly jitter points within 0 and the upper bond of the probability density function
            violin_cloud = np.empty(pdf.shape[0])
            for i in range(pdf.shape[0]):
                violin_cloud[i] = np.random.uniform(0, pdf[i])
            # To create a symmetric density/violin, we make every second point negative
            # Distributing every other point like this is also more likely to preserve the shape of the violin
            violin_cloud[::2] = violin_cloud[::2] * -1
            # Sorting by index makes it possible to merge with another df in the same order as the original one,
            # even if the index labels might differ
            return pd.concat([pd.Series(violin_cloud, index=no_na_sorted_series.index), na_series]).sort_index()

        # Prepare dataframe for filtering via Altair selection elements
        # First the rounded and raw scores are melted together separately for posted and unposted scores
        # Then they are merged into one frame and the posted and unposted score are melted together
        self.prepared_grades_for_viz = pd.merge(
            # Frame 1
            self.prepared_grades.rename(
                columns={
                    'Unposted Percent Grade': 'Submission Rounded',
                    'Unposted Exact Percent Grade': 'Exact Percent'
                }
            ).assign(
                # Computing the percentile based score on the rounded percent and with the "max" method
                # is more lenient/beneficial for students
                # since they get the max percentile value of everyone with the same score.
                # This also seems more fair since the rounded submission percentage
                # is their actual final grade in the course.
                Percentile=lambda df: df['Submission Rounded'].rank(pct=True, method='max').round(2) * 100
            # Combine the rounded and raw *unposted* scores
            ).melt(
                id_vars=['Preferred Name', 'Surname', 'Student Number', 'User ID', 'Section', 'Percentile'],
                value_vars=['Submission Rounded', 'Exact Percent'],
                value_name='Unposted Grade',
                var_name='Percent Type'
            ),
            # Frame 2
            self.prepared_grades.rename(
                columns={
                    'Percent Grade': 'Submission Rounded',
                    'Exact Percent Grade': 'Exact Percent'
                }
            # Combine the rounded and raw *posted* scores
            ).melt(
                id_vars=['Preferred Name', 'Surname', 'Student Number', 'User ID', 'Section'],
                value_vars=['Submission Rounded', 'Exact Percent'],
                value_name='Posted Grade',
                var_name='Percent Type'
            )
        # Combine the posted and unposted scores
        ).melt(
            id_vars=['Preferred Name', 'Surname', 'Student Number', 'User ID', 'Percent Type', 'Section', 'Percentile'],
            value_vars=['Unposted Grade', 'Posted Grade'],
            value_name='Percent Grade',
            var_name='Grade Status'
        # This sorting of values is required to line up the points with the violin cloud below
        ).sort_values(['User ID', 'Grade Status', 'Percent Type', 'Percent Grade'])

        # TODO fix when pandas 3.0 is released and we can use the new "stack" method
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            # This sorting of values and the index reset is required to line up the violin cloud with the df above
            self.prepared_grades_for_viz['violin_cloud'] = self.prepared_grades.sort_values(
                ['User ID', 'Percent Grade']
            ).reset_index()[[
                'Exact Percent Grade',
                'Percent Grade',
                'Unposted Exact Percent Grade',
                'Unposted Percent Grade',
            ]].apply(
                _compute_violin_cloud
            ).stack(
                dropna=False
            ).to_numpy()

        # Set up selection elements
        grade_status_dropdown = alt.binding_select(
            options=['Posted Grade', 'Unposted Grade'],
            name=' '
        )
        self.grade_status_selection = alt.selection_point(
            fields=['Grade Status'],
            bind=grade_status_dropdown,
            value=[{'Grade Status': 'Unposted Grade'}]
        )
        percent_type_dropdown = alt.binding_select(
            options=['Submission Rounded', 'Exact Percent'],
            name=' '
        )
        self.percent_type_selection = alt.selection_point(
            fields=['Percent Type'],
            bind=percent_type_dropdown,
            value=[{'Percent Type': 'Exact Percent'}]
        )
        self.search_input = alt.param(
            value='',
            bind=alt.binding(
                input='search',
                placeholder="Search name",
                name=' ',
            )
        )

        # Plot overall grade distribution

        # Constant range 50 - 100 by default
        # Since this is also used for the scale/axis domain for the boxplots
        # we need to make sure that the boxplots and bins use the same min value;
        # a power of 5 works for this since the bin step is 5 so we floor the min value to the closest 5
        bin_extent = (
            min(
                50,
                (
                    self.prepared_grades_for_viz.query(
                        '`Grade Status` == "Unposted Grade"'
                    )['Percent Grade'].min()
                    // 5
                ) * 5
            ),
            100
        )
        axis_values = list(range(int(bin_extent[0]), int(bin_extent[1]) + 1, 5))
        self.hist = alt.Chart(self.prepared_grades_for_viz, height=180, width=355).mark_bar().encode(
            alt.X('Percent Grade', bin=alt.Bin(extent=bin_extent, step=2.5), title='', axis=alt.Axis(labels=False, values=axis_values)),
            alt.Y('count()', title='Student Count')
        )

        # Plot box
        box_base = alt.Chart(
            self.prepared_grades_for_viz,
            height=20
        # The opacity setting makes sure that the scale is lined up with the hisotrgams
        # while not showing outliers
        ).mark_boxplot(outliers={'opacity': 0}, median={'color': 'black'}).encode(
            alt.X('Percent Grade', title='Final Percent Grade')
                .scale(domain=bin_extent, nice=False)
                .axis(values=axis_values),
            y=alt.value(10)
        )
        self.box = alt.layer(
            box_base,
            box_base.mark_point(size=25, shape='diamond', filled=True).encode(
                alt.X('mean(Percent Grade)', scale=alt.Scale(zero=False)),
                color=alt.value('#353535')
            ),
            # Transparent tooltip box
            box_base.transform_aggregate(
                min="min(Percent Grade)",
                max="max(Percent Grade)",
                mean="mean(Percent Grade)",
                median="median(Percent Grade)",
                q1="q1(Percent Grade)",
                q3="q3(Percent Grade)",
                count="count()",
            ).mark_bar(opacity=0).encode(
                x='q1:Q',
                x2='q3:Q',
                tooltip=alt.Tooltip(
                    ['min:Q', 'q1:Q', 'mean:Q', 'median:Q', 'q3:Q', 'max:Q', 'count:Q'],
                    format='.1f'
                )
            )
        )

        # Plot all observations
        self.strip = alt.Chart(self.prepared_grades_for_viz, height=70).mark_point(
            size=20
        ).transform_calculate(
            Name='datum["Preferred Name"] + " " + datum["Surname"]'
        ).encode(
            alt.X(
                'Percent Grade',
                title='',
                axis=alt.Axis(
                    labels=False,
                    ticks=False,
                    domain=False,
                    values=axis_values
                ),
                scale=alt.Scale(
                    zero=False,
                    nice=False,
                )
            ),
            alt.Y(
                'violin_cloud',
                scale=alt.Scale(padding=5, domain=(-1, 1)),
                axis=alt.Axis(
                    domain=False,
                    title='',
                    labels=False,
                    ticks=False,
                    grid=False
                )
            ),
            alt.Tooltip(['Name:N', 'Student Number', 'Percent Grade', 'Percentile']),
        )

        self.hover = alt.selection_point(
            fields=['User ID'], on='mouseover', nearest=True, empty=False, clear='mouseout'
        )
        self.strip_overlay = self.strip.mark_circle(size=80, opacity=1).encode(
            color=alt.value('maroon')
        ).transform_filter(
            self.hover
        )

        # This is set regardless of how many sections there are since it would be used if group-by is 'Grader' as well
        self.colorscheme_groups = [
        # Tableau without the first blue
        # since I already use that for all sections togethter
             '#f58518',
             '#e45756',
             '#72b7b2',
             '#54a24b',
             '#eeca3b',
             '#b279a2',
             '#ff9da6',
             '#9d755d',
             '#bab0ac'
        ]

        # In case "Section" is explicitly passed to group-by
        # although there is only one section
        self.section_order = (
            self.prepared_grades_for_viz
            .query('`Percent Type` == "Exact Percent" & `Grade Status` == "Unposted Grade"')
            .groupby('Section')
            ['Percent Grade']
            .median()
            .sort_values()
            .index.tolist()
        )
        # Compare sections if there are more than one (or explicitily specified)
        if self.group_by is None:
            if self.prepared_grades_for_viz['Section'].nunique() > 1:
                self.group_by = 'Section'
        if self.group_by == 'Section':
            title_sections = alt.Title(
                text=['', 'Comparison Between Sections'],
                anchor='start'
            )

            box_base_sections = alt.Chart(
                self.prepared_grades_for_viz,
                title=title_sections
            # The opacity setting makes sure that the scale is lined up with the hisotrgams
            # while not showing outliers
            ).mark_boxplot(outliers={'opacity': 0}, median={'color': 'black'}).encode(
                alt.X('Percent Grade', title='Final Percent Grade')
                    .scale(domain=bin_extent, nice=False)
                    .axis(values=axis_values),
                alt.Y(
                    'Section:N',
                    sort=self.section_order,
                    title='',
                    axis=alt.Axis(orient='right')
                ),
                alt.Color(
                    'Section:N',
                    sort=self.section_order[::-1],  # Reverse so that the highest value closest to the axis gets the most important color
                    legend=None,
                    scale=alt.Scale(range=self.colorscheme_groups)
                )
            )
            self.box_sections = alt.layer(
                box_base_sections,
                box_base_sections.mark_point(size=25, shape='diamond', filled=True).encode(
                    alt.X('mean(Percent Grade)', scale=alt.Scale(zero=False)),
                    alt.Y(
                        'Section:N',
                        sort=self.section_order,
                        title='',
                        axis=alt.Axis(orient='right')
                    ),
                    color=alt.value('#353535')
                ),
                # Transparent tooltip box
                box_base_sections.transform_aggregate(
                    min="min(Percent Grade)",
                    max="max(Percent Grade)",
                    mean="mean(Percent Grade)",
                    median="median(Percent Grade)",
                    q1="q1(Percent Grade)",
                    q3="q3(Percent Grade)",
                    count="count()",
                    groupby=['Section']
                ).mark_bar(opacity=0).encode(
                    x='q1:Q',
                    x2='q3:Q',
                    tooltip=alt.Tooltip(
                        ['min:Q', 'q1:Q', 'mean:Q', 'median:Q', 'q3:Q', 'max:Q', 'count:Q'],
                        format='.1f'
                    )
                )
            )
        return

    def layout_and_save_charts(self):
        # Add instructions
        title = alt.Title(
            text=f'Grade Distribution {self.subject} {self.course_name}',
            subtitle=[
                'Hover near a point to view student info.',
                'Hover over the box to view exact summary statistics.',
                'Changes in the dropdown menus below only affect this chart',
                '',
                ''
            ],
            anchor='start',
            dx=35
        )

        # Concatenate, add filters, and save the chart
        chart_filename = self.filename + '.html'
        alt.vconcat(
            alt.hconcat(
                alt.vconcat(
                    self.hist.add_params(
                        self.percent_type_selection,
                        self.grade_status_selection,
                        self.search_input
                    ),
                    self.strip.add_params(self.hover).transform_filter(
                        alt.expr.test(alt.expr.regexp(self.search_input, 'i'), alt.datum.Name)
                    ).interactive() + self.strip_overlay,
                    # x='shared' is required here for the `axis_values` to set the x-ticks correctly
                    # Without it, the ticks do not line up with the histogram ticks
                    alt.vconcat(
                        self.box,
                        self.box_sections
                    ).resolve_scale(x='shared') if hasattr(self, 'box_sections') else self.box,
                    spacing=0
                ).properties(
                    title=title
                ).resolve_scale(
                    x='shared'
                ).transform_filter(
                    self.percent_type_selection & self.grade_status_selection
                ),
                self.assignment_scores,
                spacing=50
            ),
            self.assignment_distributions,
            spacing=40
        ).resolve_scale(
            color='independent'
        ).configure_view(
            stroke=None
        ).save(
            chart_filename
        )
        # The label names are styled in serif by default for some reason
        with open(chart_filename, 'a') as chart_file:
            chart_file.write(
                '\n<style>'
                '\n    form.vega-bindings {'
                '\n        font-family: sans-serif;'
                '\n        font-size: 12px;'
                '\n        position: absolute;'
                '\n        opacity: 0.75;'
                '\n        display: flex;'
                '\n        gap: 5px;'
                # This could be more left when there are only two digits in the y-axis,
                # but then it looks weird with three digits
                '\n        left: 35px;'
                '\n        top: 65px;'
                '\n    }'
                '\n    input[type="search"] {'
                '\n        width: 120px;'
                '\n    }'
                '\n</style>'
            )
        click.secho(f'Grade distribution chart saved to {chart_filename}.', bold=True, fg='green')
        if self.open_chart or self.open_chart is None and click.confirm(
                'Open grade distribution chart?', default=True):
            click.launch(chart_filename)
        return

    def show_manual_grade_entry_note(self):
        """Show disclaimer and note about manual grade entry of student standings."""
        click.secho('\nNOTE', fg='yellow', bold=True)
        click.echo(
            '1. Check the output above for any warnings and notes.'
            '\n2. The saved CSV file should automatically be correctly formatted,'
            '\n   but it is ' + click.style('your responsibility to double check', bold=True) +
            '\n   since there could be unexpected changes'
            '\n   to how UBC inputs course info on Canvas.'
            '\n3. If you have students that did not take the final exam'
            '\n   you will need to enter this info manually.'
            '\n   Please see https://confluence.it.ubc.ca/display/IRPTCM/Training+Hub+for+Instructors'
            '\n   for more information on how to modify the CSV file.')
        return
