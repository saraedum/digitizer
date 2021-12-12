r"""
The svgdigitizer suite.

EXAMPLES::

    >>> from .test.cli import invoke
    >>> invoke(cli, "--help") # doctest: +NORMALIZE_WHITESPACE
    Usage: cli [OPTIONS] COMMAND [ARGS]...
      The svgdigitizer suite.
    Options:
      --help  Show this message and exit.
    Commands:
      cv        Digitize a cylic voltammogram.
      digitize  Digitize a plot.
      paginate  Render PDF pages as individual PNGs.
      plot      Display a plot of the data traced in an SVG.

"""
# ********************************************************************
#  This file is part of svgdigitizer.
#
#        Copyright (C) 2021 Albert Engstfeld
#        Copyright (C) 2021 Johannes Hermann
#        Copyright (C) 2021 Julian Rüth
#        Copyright (C) 2021 Nicolas Hörmann
#
#  svgdigitizer is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  svgdigitizer is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with svgdigitizer. If not, see <https://www.gnu.org/licenses/>.
# ********************************************************************
import click


@click.group(help=__doc__.split("EXAMPLES")[0])
def cli():
    r"""
    Entry point of the command line interface.

    This redirects to the individual commands listed below.
    """


@click.command()
@click.option(
    "--sampling_interval",
    type=float,
    default=None,
    help="Sampling interval on the x-axis.",
)
@click.argument("svg", type=click.File("rb"))
def plot(svg, sampling_interval):
    r"""
    Display a plot of the data traced in an SVG.

    EXAMPLES::

        >>> import os.path
        >>> from .test.cli import invoke, TemporaryData
        >>> with TemporaryData("**/xy.svg") as directory:
        ...     invoke(cli, "plot", os.path.join(directory, "xy.svg"))

    """
    from svgdigitizer.svg import SVG
    from svgdigitizer.svgplot import SVGPlot

    SVGPlot(SVG(svg), sampling_interval=sampling_interval).plot()


@click.command()
@click.option(
    "--sampling_interval",
    type=float,
    default=None,
    help="Sampling interval on the x-axis.",
)
@click.argument("svg", type=click.Path(exists=True))
def digitize(svg, sampling_interval):
    r"""
    Digitize a plot.

    Produces a CSV from the curve traced in the SVG.

    EXAMPLES::

        >>> import os.path
        >>> from .test.cli import invoke, TemporaryData
        >>> with TemporaryData("**/xy_rate.svg") as directory:
        ...     invoke(cli, "digitize", os.path.join(directory, "xy_rate.svg"))

    """
    from svgdigitizer.svg import SVG
    from svgdigitizer.svgplot import SVGPlot

    with open(svg, "rb") as infile:
        svg_plot = SVGPlot(SVG(infile), sampling_interval=sampling_interval)

    from pathlib import Path
    svg_plot.df.to_csv(Path(svg).with_suffix(".csv"), index=False)


@click.command(name="cv")
@click.option(
    "--sampling_interval",
    type=float,
    default=None,
    help="sampling interval on the x-axis in volt (V)",
)
@click.option(
    "--metadata", type=click.File("rb"), default=None, help="yaml file with metadata"
)
@click.option("--package", is_flag=True, help="create .json in data package format")
@click.option(
    "--outdir",
    type=click.Path(file_okay=False),
    default=None,
    help="write output files to this directory",
)
@click.argument("svg", type=click.Path(exists=True))
def digitize_cv(svg, sampling_interval, metadata, package, outdir):
    r"""
    Digitize a cylic voltammogram.

    For inclusion in the echemdb.

    EXAMPLES::

        >>> import os.path
        >>> from .test.cli import invoke, TemporaryData
        >>> with TemporaryData("**/xy_rate.svg") as directory:
        ...     invoke(cli, "cv", os.path.join(directory, "xy_rate.svg"))

    TESTS:

    The command can be invoked on files in the current directory::

        >>> import os, os.path
        >>> from .test.cli import invoke, TemporaryData
        >>> cwd = os.getcwd()
        >>> with TemporaryData("**/xy_rate.svg") as directory:
        ...     os.chdir(directory)
        ...     try:
        ...         invoke(cli, "cv", "xy_rate.svg")
        ...     finally:
        ...         os.chdir(cwd)

    The command can be invoked without sampling when data is not given in volts::

        >>> import os.path
        >>> from .test.cli import invoke, TemporaryData
        >>> from svgdigitizer.svg import SVG
        >>> from svgdigitizer.svgplot import SVGPlot
        >>> from svgdigitizer.electrochemistry.cv import CV
        >>> with TemporaryData("**/xy_rate.svg") as directory:
        ...     print(CV(SVGPlot(SVG(open(os.path.join(directory, "xy_rate.svg"))))).x_label.unit)
        mV
        >>> with TemporaryData("**/xy_rate.svg") as directory:
        ...     invoke(cli, "cv", os.path.join(directory, "xy_rate.svg"))

    """
    import os.path

    import yaml
    from astropy import units as u

    from svgdigitizer.electrochemistry.cv import CV
    from svgdigitizer.svg import SVG
    from svgdigitizer.svgplot import SVGPlot

    if outdir is None:
        outdir = os.path.dirname(svg)
    if outdir.strip() == "":
        outdir = "."

    import os

    os.makedirs(str(outdir), exist_ok=True)

    # Determine unit of the voltage scale.
    with open(svg, "rb") as infile:
        cv = CV(SVGPlot(SVG(infile)))
        xunit = CV.get_axis_unit(cv.x_label.unit)

    if sampling_interval is not None and xunit != u.V:
        # Determine conversion factor to volts.
        sampling_correction = xunit.to(u.V)
        sampling_interval = sampling_interval / sampling_correction

    if metadata:
        metadata = yaml.load(metadata, Loader=yaml.SafeLoader)

    with open(svg, "rb") as infile:
        cv = CV(
            SVGPlot(SVG(infile), sampling_interval=sampling_interval),
            metadata=metadata,
        )

    from pathlib import Path

    csvname = Path(svg).with_suffix(".csv").name

    cv.df.to_csv(os.path.join(outdir, csvname), index=False)

    if package:
        from datapackage import Package

        package = Package(cv.metadata, base_path=outdir)
        package.infer(csvname)

    from datetime import date, datetime

    def defaultconverter(item):
        if isinstance(item, (datetime, date)):
            return item.__str__()
        return None

    import json

    with open(
        os.path.join(outdir, Path(svg).with_suffix(".json").name), "w", encoding='utf-8',
    ) as outfile:
        json.dump(
            package.descriptor if package else cv.metadata, outfile, default=defaultconverter
        )


@click.command()
@click.option("--onlypng", is_flag=True, help="Only produce png files")
@click.argument("pdf")
def paginate(onlypng, pdf):
    r"""
    Render PDF pages as individual PNGs.

    The PNGs are written to the PDFs directory as 0.png, 1.png, ….

    EXAMPLES::

        >>> import os.path
        >>> from .test.cli import invoke, TemporaryData
        >>> with TemporaryData("**/mustermann_2021_svgdigitizer_1.pdf") as directory:
        ...     invoke(cli, "paginate", os.path.join(directory, "mustermann_2021_svgdigitizer_1.pdf"))

    """
    import svgwrite
    from pdf2image import convert_from_path
    from PIL import Image
    from svgwrite.extensions.inkscape import Inkscape

    basename = pdf.split(".")[0]
    pages = convert_from_path(pdf, dpi=600)
    for idx, page in enumerate(pages):
        base_image_path = f"{basename}_p{idx}"
        page.save(f"{base_image_path}.png", "PNG")
        if not onlypng:
            image = Image.open(f"{base_image_path}.png")
            width, height = image.size
            dwg = svgwrite.Drawing(
                f"{base_image_path}.svg",
                size=(f"{width}px", f"{height}px"),
                profile="full",
            )
            Inkscape(dwg)
            img = dwg.add(
                svgwrite.image.Image(
                    f"{base_image_path}.png",
                    insert=(0, 0),
                    size=(f"{width}px", f"{height}px"),
                )
            )

            # workaround: add missing locking attribute for image element
            # https://github.com/mozman/svgwrite/blob/c8cbf6f615910b3818ccf939fce0e407c9c789cb/svgwrite/extensions/inkscape.py#L50
            elements = dwg.validator.elements
            elements["image"].valid_attributes = {
                "sodipodi:insensitive",
            } | elements["image"].valid_attributes
            img.attribs["sodipodi:insensitive"] = "true"

            dwg.save(pretty=True)


cli.add_command(plot)
cli.add_command(digitize)
cli.add_command(digitize_cv)
cli.add_command(paginate)

# Register command docstrings for doctesting.
# Since commands are not fnuctions anymore due to their decorator, their
# docstrings would otherwise be ignored.
__test__ = {
    name: command.__doc__ for (name, command) in cli.commands.items() if command.__doc__
}

if __name__ == "__main__":
    cli()
