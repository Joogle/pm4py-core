import gzip
import pkgutil
from enum import Enum
from io import BytesIO

from pm4py.objects.log.util import xes as xes_util
from pm4py.util import exec_utils, constants


class Parameters(Enum):
    COMPRESS = "compress"
    SHOW_PROGRESS_BAR = "show_progress_bar"
    ENCODING = "encoding"


# defines correspondence between Python types and XES types
__TYPE_CORRESPONDENCE = {
    "str": xes_util.TAG_STRING,
    "int": xes_util.TAG_INT,
    "float": xes_util.TAG_FLOAT,
    "datetime": xes_util.TAG_DATE,
    "Timestamp": xes_util.TAG_DATE,
    "bool": xes_util.TAG_BOOLEAN,
    "dict": xes_util.TAG_LIST
}
# if a type is not found in the previous list, then default to string
__DEFAULT_TYPE = xes_util.TAG_STRING


def __get_xes_attr_type(attr_type):
    """
    Transform a Python attribute type (e.g. str, datetime) into a XES attribute type (e.g. string, date)

    Parameters
    ----------
    attr_type:
        Python attribute type
    """
    if attr_type in __TYPE_CORRESPONDENCE:
        attr_type_xes = __TYPE_CORRESPONDENCE[attr_type]
    else:
        attr_type_xes = __DEFAULT_TYPE
    return attr_type_xes


def __get_xes_attr_value(attr_value, attr_type_xes):
    """
    Transform an attribute value from Python format to XES format (the type is provided as argument)

    Parameters
    ----------
    attr_value:
        XES attribute value
    attr_type_xes:
        XES attribute type

    """
    if attr_type_xes == xes_util.TAG_DATE:
        return attr_value.isoformat()
    elif attr_type_xes == xes_util.TAG_BOOLEAN:
        return str(attr_value).lower()
    return str(attr_value)


def get_tab_indent(n):
    """
    Get the desidered number of indentations as string

    Parameters
    -------------
    n
        Number of indentations

    Returns
    -------------
    str_tab_indent
        Desidered number of indentations as string
    """
    return "".join(["\t"] * n)


def export_attribute(attr_name, attr_value, indent_level):
    """
    Exports an attribute

    Parameters
    --------------
    attr_name
        Name of the attribute
    attr_value
        Value of the attribute
    indent_level
        Level of indentation

    Returns
    --------------
    stru
        String representing the content of the attribute
    """
    ret = []
    attr_type = __get_xes_attr_type(type(attr_value).__name__)
    if not attr_type == xes_util.TAG_LIST:
        attr_value = __get_xes_attr_value(attr_value, attr_type)
        ret.append(get_tab_indent(
            indent_level) + "<%s key=\"%s\" value=\"%s\" />\n" % (attr_type, attr_name, attr_value))
    else:
        if attr_value[xes_util.KEY_VALUE] is None:
            # list
            ret.append(get_tab_indent(indent_level) + "<list key=\"%s\">\n" % (attr_name))
            ret.append(get_tab_indent(indent_level + 1) + "<values>\n")
            for subattr in attr_value[xes_util.KEY_CHILDREN]:
                ret.append(export_attribute(subattr[0], subattr[1], indent_level + 2))
            ret.append(get_tab_indent(indent_level + 1) + "</values>\n")
            ret.append(get_tab_indent(indent_level) + "</list>\n")
        else:
            # nested attribute
            this_value = attr_value[xes_util.KEY_VALUE]
            this_type = __get_xes_attr_type(type(this_value).__name__)
            this_value = __get_xes_attr_value(this_value, this_type)
            ret.append(get_tab_indent(
                indent_level) + "<%s key=\"%s\" value=\"%s\">\n" % (this_type, attr_name, this_value))
            for subattr_name, subattr_value in attr_value[xes_util.KEY_CHILDREN].items():
                ret.append(export_attribute(subattr_name, subattr_value, indent_level + 1))
            ret.append("</%s>\n" % this_type)
    return "".join(ret)


def export_log_line_by_line(log, fp_obj, encoding, parameters=None):
    """
    Exports the contents of the log line-by-line
    to a file object

    Parameters
    --------------
    log
        Event log
    fp_obj
        File object
    encoding
        Encoding
    parameters
        Parameters of the algorithm
    """
    if parameters is None:
        parameters = {}

    show_progress_bar = exec_utils.get_param_value(Parameters.SHOW_PROGRESS_BAR, parameters, True)

    progress = None
    if pkgutil.find_loader("tqdm") and show_progress_bar:
        from tqdm.auto import tqdm
        progress = tqdm(total=len(log), desc="exporting log, completed traces :: ")

    fp_obj.write(("<?xml version=\"1.0\" encoding=\"" + encoding + "\" ?>\n").encode(
        encoding))
    fp_obj.write(("<log>\n").encode(encoding))
    for ext_name, ext_value in log.extensions.items():
        fp_obj.write((get_tab_indent(1) + "<extension name=\"%s\" prefix=\"%s\" uri=\"%s\" />\n" % (
            ext_name, ext_value[xes_util.KEY_PREFIX], ext_value[xes_util.KEY_URI])).encode(encoding))
    for clas_name, clas_attributes in log.classifiers.items():
        fp_obj.write((get_tab_indent(1) + "<classifier name=\"%s\" keys=\"%s\" />\n" % (
            clas_name, " ".join(clas_attributes))).encode(encoding))
    for attr_name, attr_value in log.attributes.items():
        fp_obj.write(export_attribute(attr_name, attr_value, 1).encode(encoding))
    for scope in log.omni_present:
        fp_obj.write((get_tab_indent(1) + "<global scope=\"%s\">\n" % (scope)).encode(encoding))
        for attr_name, attr_value in log.omni_present[scope].items():
            fp_obj.write(export_attribute(attr_name, attr_value, 2).encode(encoding))
        fp_obj.write((get_tab_indent(1) + "</global>\n").encode(encoding))
    for trace in log:
        fp_obj.write((get_tab_indent(1) + "<trace>\n").encode(encoding))
        for attr_name, attr_value in trace.attributes.items():
            fp_obj.write(export_attribute(attr_name, attr_value, 2).encode(encoding))
        for event in trace:
            fp_obj.write((get_tab_indent(2) + "<event>\n").encode(encoding))
            for attr_name, attr_value in event.items():
                fp_obj.write(export_attribute(attr_name, attr_value, 3).encode(encoding))
            fp_obj.write((get_tab_indent(2) + "</event>\n").encode(encoding))
        fp_obj.write((get_tab_indent(1) + "</trace>\n").encode(encoding))
        if progress is not None:
            progress.update()

    # gracefully close progress bar
    if progress is not None:
        progress.close()
    del progress

    fp_obj.write("</log>\n".encode(encoding))


def apply(log, output_file_path, parameters=None):
    """
    Exports a XES log using a non-standard exporter
    (classifiers, lists, nested attributes, globals, extensions are not supported)

    Parameters
    ------------
    log
        Event log
    output_file_path
        Path to the XES file
    parameters
        Parameters
    """
    if parameters is None:
        parameters = {}

    encoding = exec_utils.get_param_value(Parameters.ENCODING, parameters, constants.DEFAULT_ENCODING)
    compress = exec_utils.get_param_value(Parameters.COMPRESS, parameters, output_file_path.lower().endswith(".gz"))

    if compress:
        if not output_file_path.lower().endswith(".gz"):
            output_file_path = output_file_path + ".gz"
        f = gzip.open(output_file_path, mode="wb")
    else:
        f = open(output_file_path, "wb")

    export_log_line_by_line(log, f, encoding, parameters=parameters)

    f.close()


def export_log_as_string(log, parameters=None):
    """
    Export a log into a string

    Parameters
    -----------
    log: :class:`pm4py.log.log.EventLog`
        PM4PY log
    parameters
        Parameters of the algorithm

    Returns
    -----------
    logString
        Log as a string
    """
    if parameters is None:
        parameters = {}

    encoding = exec_utils.get_param_value(Parameters.ENCODING, parameters, constants.DEFAULT_ENCODING)
    compress = exec_utils.get_param_value(Parameters.COMPRESS, parameters, False)

    b = BytesIO()

    if compress:
        d = gzip.GzipFile(fileobj=b, mode="wb")
    else:
        d = b

    export_log_line_by_line(log, d, encoding, parameters=parameters)

    if compress:
        d.close()

    return b.getvalue()