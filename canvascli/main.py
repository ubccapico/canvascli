"""A CLI to reformat and review Canvas grades.
See the README and class docstrings for more info.
"""
import getpass
import os
from collections import defaultdict
from requests.exceptions import MissingSchema

import altair as alt
import click
import pandas as pd
from canvasapi import Canvas
from canvasapi.exceptions import InvalidAccessToken, Unauthorized
# Using https://github.com/biqqles/dataclassy instead of dataclasses from
# stdlibto allow for dataclass inheritance when there are default values. Could
# use a custom init but it gets messy and the advantage of using dataclasses is
# lost. Dataclass inheritance might be fixed in 3.10
# https://bugs.python.org/issue36077
from dataclassy import dataclass
from . import __version__


@click.group()
@click.version_option(version=__version__, prog_name='canvascli')
def cli():
    """A CLI to reformat and review Canvas grades.

    \b
    Examples:
        # Download grades from canvas and convert them to FSC format
        canvascli prepare-fsc-grades --course-id 53665
        \b
        # Show courses accessible by the given API token
        canvascli show-courses

    See the --help for each subcommand for more options.

    If you don't want to be prompted for your Canvas API token,
    you can save it to an environmental variable named CANVAS_PAT.
    """
    return


@cli.command()
@click.option('--course-id', default=None, required=True, help='Canvas id'
              ' of the course to' ' download grades from, e.g. 53665. This id'
              ' can be found by running `canvascli show-courses`'
              "(and in the course's canvas page URL). Default: None")
@click.option('--filename', default=None, help='Name of the saved file and chart'
              ' (without file extension). Default: Automatic based on the course.')
@click.option('--api-url', default='https://canvas.ubc.ca', help='Base canvas URL.'
              ' Default: https://canvas.ubc.ca')
@click.option('--student-status', default='active', help='Which types of students'
              ' to download grades for. Default: active')
@click.option('--drop-student-numbers', default=None, help='Student numbers to drop,'
              ' in quotes separated by spaces, e.g. "14391238 30329123".'
              ' Useful for removing specific students. Default: None')
@click.option('--drop-grade-threshold', default=0, help='Students with grades <='
              ' this threshold are dropped. Useful for removing test students'
              ' and students that dropped the course after completing some work.'
              ' Default: 0')
@click.option('--drop-na', default=True, help='Whether to drop students'
              ' that are missing info such as student number.'
              ' Useful for only removing test students. Default: True')
@click.option('--open-chart', default=None, type=bool, help='Whether to open'
              ' the grade distribution chart automatically.'
              ' Default: Ask at the end')
def prepare_fsc_grades(course_id, filename, api_url, student_status,
                       drop_student_numbers, drop_grade_threshold, drop_na,
                       open_chart):
    """Prepare course grades for FSC submission.
    \b
    Downloads grades from a canvas course and convert them to the format
    required by the FSC for submission of final grades.

    Drops students with missing info or 0 grade by default.

    A CSV file is saved in the current directory,
    which can be uploaded directly to FSC.

    A grade distribution chart is saved in the current directory.

    \b
    Examples:
        # Download grades from canvas and convert them to FSC format
        canvascli prepare_fsc_grades --course-id 53665
        \b
        # Give a custom file name and drop a specific student
        canvascli prepare_fsc_grades --course-id 53665 --drop-students "43659202"
    """
    fsc_grades = FscGrades(
        course_id, filename, api_url, student_status, drop_student_numbers,
        drop_grade_threshold, drop_na, open_chart)
    fsc_grades.connect_to_canvas()
    fsc_grades.connect_to_course()
    fsc_grades.get_canvas_grades()
    fsc_grades.drop_students()
    fsc_grades.convert_grades_to_fsc_format()
    fsc_grades.save_fsc_grades_to_file()
    fsc_grades.plot_fsc_grade_distribution()
    fsc_grades.show_manual_grade_entry_note()
    return


@cli.command()
@click.option('--api-url', default='https://canvas.ubc.ca', help='Base canvas URL.'
              ' Default: https://canvas.ubc.ca')
@click.option('--filter', 'filter_', default='', help='Only show courses including'
              ' this string (case insensitve). Useful to narrow down the displayed'
              ' results. Default: "" (matches all courses)')
def show_courses(api_url, filter_):
    """Show courses accessible by the given API token.

    Examples:
        \b
        # Show all courses
        canvascli show-courses
        \b
        # Show only courses including the string "541"
        canvascli show-courses --filter 541
    """
    accessible_courses = AccessibleCourses(api_url, filter_)
    accessible_courses.connect_to_canvas()
    accessible_courses.download_courses()
    accessible_courses.filter_and_show_courses()
    return


@cli.command()
def z_compare_TA_grading():
    """**Not yet implemented**"""
    return


@cli.command()
def z_review_student_grades():
    """**Not yet implemented**"""
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
            click.echo('Paste your canvas API token and press enter:')
            self.api_token = getpass.getpass()
        self.canvas = Canvas(self.api_url, self.api_token)
        return


@dataclass
class AccessibleCourses(CanvasConnection):
    """Show all courses accessible from a specific API token."""
    api_url: str
    filter_: str

    def download_courses(self):
        """Download all courses accessible from a specific API token."""
        self.courses = defaultdict(list)
        try:
            for course in self.canvas.get_courses():
                self.courses['id'].append(course.id)
                self.courses['name'].append(course.name)
        # Show common exceptions in a way that is easy to understand
        except MissingSchema:
            raise SystemExit(self.invalid_canvas_url_msg)
        except InvalidAccessToken:
            raise SystemExit(self.invalid_canvas_api_token_msg.format(self.api_token))
        return

    def filter_and_show_courses(self):
        """Filter and show downloaded courses."""
        click.echo("Your API token has access to the following courses:\n")
        click.echo(
            pd.DataFrame(self.courses)
            .query('name.str.contains(@self.filter_, case=False)', engine='python')
            .to_markdown(index=False))
        return


@dataclass
class FscGrades(CanvasConnection):
    """Prepare FSC grades for a specific course."""
    course_id: int
    filename: str
    api_url: str
    student_status: str
    drop_student_numbers: str
    drop_grade_threshold: int
    drop_na: bool
    open_chart: bool
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
            self.filename = (f'fsc-grades_{self.course.course_code.replace(" ", "-")}'
                             .replace('/', '-'))
        return

    def get_canvas_grades(self):
        """Download grades from a canvas course."""
        click.echo('Downloading student grades...')
        enrollments = self.course.get_enrollments(type=['StudentEnrollment'], state=[self.student_status])
        canvas_grades = defaultdict(list)
        for enrollment in enrollments:
            canvas_grades['Student Number'].append(enrollment.user['sis_user_id'])
            surname, preferred_name = enrollment.user['sortable_name'].split(', ')
            canvas_grades['Surname'].append(surname)
            canvas_grades['Preferred Name'].append(preferred_name)
            canvas_grades['Percent Grade'].append(enrollment.grades['final_score'])
        self.canvas_grades = pd.DataFrame(canvas_grades)
        return

    def drop_students(self):
        """Drop unwanted students entries such as test students and dropouts."""
        # Drop students under the grade thresholds
        # Test accounts and students who dropped the course often have a grade of zero
        dropped_students = self.canvas_grades.query(
            '`Percent Grade` <= @self.drop_grade_threshold')
        self.canvas_grades = self.canvas_grades.query(
            '`Percent Grade` > @self.drop_grade_threshold').copy()

        # Drop students that have missing info in any field
        # These are also printed so that it is clear to the user what has happened
        # and they need to be explicit in disabling the beahvior instead of
        # accidentally uploading empty fields to FSC.
        if self.drop_na:
            dropped_students = dropped_students.append(
                self.canvas_grades[self.canvas_grades.isna().any(axis=1)])
            self.canvas_grades = self.canvas_grades.dropna()

        # Drop students explicitly
        if self.drop_student_numbers is not None:
            dropped_students = dropped_students.append(
                self.canvas_grades.query(
                    '`Student Number` in @self.drop_student_numbers.split()'))
            self.canvas_grades = self.canvas_grades.query(
                '`Student Number` not in @self.drop_student_numbers.split()').copy()

        # Display the dropped students so the user can catch errors easily
        if dropped_students.shape[0] > 0:
            click.echo(f'Dropping {dropped_students.shape[0]} student(s) with'
                       f' missing information or a grade <= {self.drop_grade_threshold}:\n')
            click.echo(dropped_students.to_markdown(index=False))
            click.echo()
        return

    def convert_grades_to_fsc_format(self):
        """Convert grades to FSC format."""
        # Add required FSC info
        # This could be made more flexible in the future if needed, but LT hub
        # mentioned that these fields should be safe to extract from the canvas
        # course code (for UBC courses in general).
        self.fsc_grades = self.canvas_grades.copy()
        self.fsc_grades[['Subject', 'Course', 'Section', 'Session']] = self.course.course_code.split()
        self.fsc_grades[['Campus', 'Standing', 'Standing Reason']] = ['UBC', '', '']
        # Reorder columns to match the required FSC format
        self.fsc_grades = self.fsc_grades[[
            'Session', 'Campus', 'Student Number', 'Subject', 'Course', 'Section',
            'Surname', 'Preferred Name', 'Standing', 'Standing Reason', 'Percent Grade']]
        return

    def save_fsc_grades_to_file(self):
        """Write a CSV file that can be uploaded to FSC."""
        self.fsc_grades.to_csv(self.filename + '.csv', index=False)
        click.echo(f'Grades saved to {self.filename}.csv.')
        return

    def plot_fsc_grade_distribution(self):
        """Create a histogram and interactive strip chart for the grade distribution"""
        hist = alt.Chart(self.fsc_grades, height=200).mark_bar().encode(
            alt.X('Percent Grade', bin=True),
            alt.Y('count()'))
        strip = alt.Chart(self.fsc_grades, height=50).mark_point(size=20).transform_calculate(
            # Generate Gaussian jitter with a Box-Muller transform
            jitter='sqrt(-2*log(random()))*cos(2*PI*random())',
            Name='datum["Preferred Name"] + " " + datum["Surname"]'
        ).encode(
            alt.X('Percent Grade', scale=alt.Scale(zero=False)),
            alt.Y('jitter:Q', scale=alt.Scale(nice=True), axis=alt.Axis(
                domain=True, title='', labels=False, ticks=False, grid=False)),
            alt.Tooltip(['Name:N', 'Student Number', 'Percent Grade'])).interactive()
        chart = hist & strip
        title = alt.TitleParams(
            text='Grade distribution',
            subtitle=[
                'Hover over the points to see the student name and grade.',
                'Zoom with the mouse wheel and double click to reset the view.',
                'Click the three dots button to the right to save the plot.'])
        chart_filename = self.filename + '.html'
        chart.properties(title=title).save(chart_filename)
        click.echo(f'Grade distribution chart saved to {chart_filename}.')
        if self.open_chart or self.open_chart is None and click.confirm('Open grade distribution chart?', default=True):
            click.launch(chart_filename)
        return

    def show_manual_grade_entry_note(self):
        """Show disclaimer and note about manual grade entry of student standings."""
        click.echo(
            '\nNote:\nThe saved CSV file should automatically be correctly formatted,'
            '\nbut it is a good idea to double check in case there are unexpected changes'
            '\nto how UBC inputs course info on Canvas.'
            '\nIf you have students that did not take the final exam'
            '\nor with a thesis in progress, you will need to enter this info manually.'
            '\nPlease see https://facultystaff.students.ubc.ca/files/FSCUserGuide.pdf'
            '\nunder "Acceptable Values for Grades Entry" for how to modify the CSV file.')
        return
