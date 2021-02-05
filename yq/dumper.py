import re
from collections import OrderedDict

import yaml

from .loader import hash_key

class OrderedIndentlessDumper(yaml.SafeDumper):
    pass

class OrderedDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(OrderedDumper, self).increase_indent(flow, False)

yaml_value_annotation_re = re.compile(r"^__yq_(?P<type>tag|style)_(?P<key>.+)__$")
yaml_item_annotation_re = re.compile(r"^__yq_(?P<type>tag|style)_(?P<key>\d+)_(?P<value>.+)__$")

def get_dumper(use_annotations=False, indentless=False):
    def represent_dict(dumper, data):
        pairs, custom_styles, custom_tags = [], {}, {}
        for k, v in data.items():
            if use_annotations and isinstance(k, str):
                value_annotation = yaml_value_annotation_re.match(k)
                if value_annotation and value_annotation.group("type") == "style":
                    custom_styles[value_annotation.group("key")] = v
                    continue
                elif value_annotation and value_annotation.group("type") == "tag":
                    custom_tags[value_annotation.group("key")] = v
                    continue
            pairs.append((k, v))
        mapping = dumper.represent_mapping("tag:yaml.org,2002:map", pairs)
        if use_annotations:
            for k, v in mapping.value:
                hashed_key = hash_key(k.value)
                if hashed_key in custom_styles:
                    if isinstance(v, yaml.nodes.ScalarNode):
                        v.style = custom_styles[hashed_key]
                    elif custom_styles[hashed_key] == "flow":
                        v.flow_style = True
                if hashed_key in custom_tags:
                    v.tag = custom_tags[hashed_key]
        return mapping

    def represent_list(dumper, data):
        raw_list, custom_styles, custom_tags = [], {}, {}
        for v in data:
            if use_annotations and isinstance(v, str):
                annotation = yaml_item_annotation_re.match(v)
                if annotation and annotation.group("type") == "style":
                    custom_styles[annotation.group("key")] = annotation.group("value")
                    continue
                elif annotation and annotation.group("type") == "tag":
                    custom_tags[annotation.group("key")] = annotation.group("value")
                    continue
            raw_list.append(v)
        sequence = dumper.represent_list(raw_list)
        if use_annotations:
            for i, v in enumerate(sequence.value):
                if str(i) in custom_styles:
                    if isinstance(v, yaml.nodes.ScalarNode):
                        v.style = custom_styles[str(i)]
                    elif custom_styles[str(i)] == "flow":
                        v.flow_style = True
                if str(i) in custom_tags:
                    v.tag = custom_tags[str(i)]
        return sequence

    dumper = OrderedIndentlessDumper if indentless else OrderedDumper
    dumper.add_representer(OrderedDict, represent_dict)
    dumper.add_representer(list, represent_list)
    return dumper
