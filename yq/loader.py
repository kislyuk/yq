import yaml
from base64 import b64encode
from collections import OrderedDict
from hashlib import sha224

def hash_key(key):
    return b64encode(sha224(key.encode() if isinstance(key, str) else key).digest()).decode()

class OrderedLoader(yaml.SafeLoader):
    pass

def get_loader(use_annotations=False):
    def construct_sequence(loader, node):
        annotations = []
        for i, v_node in enumerate(node.value):
            if not use_annotations:
                break
            if v_node.tag and v_node.tag.startswith("!") and not v_node.tag.startswith("!!") and len(v_node.tag) > 1:
                annotations.append("__yq_tag_{}_{}__".format(i, v_node.tag))
            if isinstance(v_node, yaml.nodes.ScalarNode) and v_node.style:
                annotations.append("__yq_style_{}_{}__".format(i, v_node.style))
            elif isinstance(v_node, (yaml.nodes.SequenceNode, yaml.nodes.MappingNode)) and v_node.flow_style is True:
                annotations.append("__yq_style_{}_{}__".format(i, "flow"))
        return [loader.construct_object(i) for i in node.value] + annotations

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)  # TODO: is this needed?
        pairs = []
        for k_node, v_node in node.value:
            key = loader.construct_object(k_node)
            value = loader.construct_object(v_node)
            pairs.append((key, value))
            if not (use_annotations and isinstance(key, (str, bytes))):
                continue
            if v_node.tag and v_node.tag.startswith("!") and not v_node.tag.startswith("!!") and len(v_node.tag) > 1:
                pairs.append(("__yq_tag_{}__".format(hash_key(key)), v_node.tag))
            if isinstance(v_node, yaml.nodes.ScalarNode) and v_node.style:
                pairs.append(("__yq_style_{}__".format(hash_key(key)), v_node.style))
            elif isinstance(v_node, (yaml.nodes.SequenceNode, yaml.nodes.MappingNode)) and v_node.flow_style is True:
                pairs.append(("__yq_style_{}__".format(hash_key(key)), "flow"))
        return OrderedDict(pairs)

    def parse_unknown_tags(loader, tag_suffix, node):
        if isinstance(node, yaml.nodes.ScalarNode):
            return loader.construct_scalar(node)
        elif isinstance(node, yaml.nodes.SequenceNode):
            return construct_sequence(loader, node)
        elif isinstance(node, yaml.nodes.MappingNode):
            return construct_mapping(loader, node)

    OrderedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    OrderedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG, construct_sequence)
    OrderedLoader.add_multi_constructor('', parse_unknown_tags)
    return OrderedLoader
