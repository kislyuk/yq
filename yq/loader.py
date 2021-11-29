from base64 import b64encode
from hashlib import sha224

import yaml
from yaml.tokens import AliasToken, AnchorToken, ScalarToken
try:
    from yaml import CSafeLoader as default_loader
except ImportError:
    from yaml import SafeLoader as default_loader

def hash_key(key):
    return b64encode(sha224(key.encode() if isinstance(key, str) else key).digest()).decode()


class CustomLoader(yaml.SafeLoader):
    expand_aliases = False

    def fetch_alias(self):
        if self.expand_aliases:
            return super().fetch_alias()
        self.save_possible_simple_key()
        self.allow_simple_key = False
        alias_token = self.scan_anchor(AliasToken)
        # FIXME: turning alias into a string is not ideal, but probably the only reasonable solution
        # FIXME: use magic tags (__yq_alias/__yq_anchor) to preserve with -Y
        self.tokens.append(ScalarToken(value='*' + alias_token.value,
                                       plain=True,
                                       start_mark=alias_token.start_mark,
                                       end_mark=alias_token.end_mark))

    def fetch_anchor(self):
        if self.expand_aliases:
            return super().fetch_anchor()
        self.save_possible_simple_key()
        self.allow_simple_key = False
        self.scan_anchor(AnchorToken)

def get_loader(use_annotations=False, expand_aliases=True):
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
        return dict(pairs)

    def parse_unknown_tags(loader, tag_suffix, node):
        if isinstance(node, yaml.nodes.ScalarNode):
            return loader.construct_scalar(node)
        elif isinstance(node, yaml.nodes.SequenceNode):
            return construct_sequence(loader, node)
        elif isinstance(node, yaml.nodes.MappingNode):
            return construct_mapping(loader, node)

    loader_class = default_loader if expand_aliases else CustomLoader
    loader_class.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    loader_class.add_constructor(yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG, construct_sequence)
    loader_class.add_multi_constructor('', parse_unknown_tags)
    return loader_class
