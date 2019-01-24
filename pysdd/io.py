# -*- coding: UTF-8 -*-
"""
pysdd.io
~~~~~~~~

:author: Wannes Meert, Arthur Choi
:copyright: Copyright 2017-2019 KU Leuven and Regents of the University of California.
:license: Apache License, Version 2.0, see LICENSE for details.
"""
MYPY = False
if MYPY:
    from .sdd import SddNode, Vtree
    from typing import List, Optional, Dict, Set, Union, Tuple
    LitNameMap = Dict[Union[int, str], str]


node_count = 0


def sdd_to_dot(node, litnamemap=None, show_id=False, merge_leafs=False):
    # type: (SddNode, Optional[LitNameMap], bool, bool) -> str
    """Generate (alternative) Graphviz DOT string for SDD with given root.

    :param node: Root node for graph
    :param litnamemap: Dictionary for node labels. For variable 1 the keys are 1 and -1 for positive and negative.
        For multiplication and addition the keys are 'mult' and 'add'. And for true and false, the keys are 'true'
        and 'false'.
    :param show_id: Show internal node ids, useful for debugging
    :param merge_leafs: Variable nodes are shown multiple times to improve the visualisation. Set this argument
        to True to disable this.
    """
    global node_count
    node_count = 0
    if litnamemap is None:
        litnamemap = {}
    if node is None:
        raise ValueError("No root node given")
    s = [
        "digraph sdd {"
    ]
    visited = set()
    nodeid, root_s = _sddnode_to_dot_int(node, visited, litnamemap, show_id, merge_leafs)
    s += root_s
    s += [
        "}"
    ]
    return "\n".join(s)


def _format_sddnode_label(node, name=None, litnamemap=None):
    # type: (SddNode, Optional[str], Optional[LitNameMap]) -> str
    if name is not None:
        pass
    elif node.is_true():
        name = litnamemap.get("true", "⟙")
    elif node.is_false():
        name = litnamemap.get("false", "⟘")
    else:
        name = node.literal
    if litnamemap is not None:
        name = litnamemap.get(name, name)
    return f"{name}"


def _format_sddnode_xlabel(node):
    # type: (SddNode) -> str
    if node.vtree() is not None:
        vtree_pos = node.vtree().position()
    else:
        vtree_pos = "n"
    return f"Id:{node.id}\\nVp:{vtree_pos}"


def _sddnode_to_dot_int(node, visited, litnamemap=None, show_id=False, merge_leafs=False):
    # type: (SddNode, Set[SddNode], Optional[LitNameMap], bool, bool) -> Tuple[str, List[str]]
    if node in visited:
        return str(node.id), []
    if node.is_false() or node.is_true() or node.is_literal():
        # Leaf node
        if merge_leafs:
            visited.add(node)
        label = _format_sddnode_label(node, None, litnamemap)
        extra_options = ""
        if show_id:
            extra_options += (",xlabel=\"" + _format_sddnode_xlabel(node) + "\"")
        if merge_leafs:
            nodeid = str(node.id)
        else:
            global node_count
            nodeid = f"n{node_count}_{node.id}"
            node_count += 1
        return nodeid, [f"{nodeid} [shape=rectangle,label=\"{label}\"{extra_options}];"]
    elif node.is_decision():
        # Decision node
        visited.add(node)
        extra_options = ""
        if show_id:
            extra_options += (",xlabel=\"" + _format_sddnode_xlabel(node) + "\"")
        nodeid = str(node.id)
        s = [f"{nodeid} [shape=circle,label=\"{litnamemap.get('add', '+')}\"{extra_options}];"]
        for idx, (prime, sub) in enumerate(node.elements()):
            prime_id, prime_s = _sddnode_to_dot_int(prime, visited, litnamemap, show_id, merge_leafs)
            sub_id, sub_s = _sddnode_to_dot_int(sub, visited, litnamemap, show_id, merge_leafs)
            ps_id = "ps_{}_{}".format(node.id, idx)
            s += [
                f"{ps_id} [shape=circle, label=\"{litnamemap.get('mult', '×')}\"];",
                "{} -> {} [arrowhead=none];".format(node.id, ps_id),
                "{} -> {};".format(ps_id, prime_id),
                "{} -> {};".format(ps_id, sub_id),
            ]
            s += prime_s
            s += sub_s
        return nodeid, s


def vtree_to_dot(vtree, litnamemap=None, show_id=False):
    # type: (Vtree, Optional[LitNameMap], bool) -> str
    """Generate (alternative) Graphviz DOT string for given Vtree."""
    s = [
        "digraph vtree {"
    ]
    s += _vtree_to_dot_int(vtree, litnamemap, show_id)
    s += [
        "}"
    ]
    return "\n".join(s)


def _vtree_to_dot_int(vtree, litnamemap=None, show_id=False):
    # type: (Vtree, Optional[LitNameMap], bool) -> List[str]
    s = []
    left = vtree.left()
    right = vtree.right()
    if left is None and right is None:
        name = vtree.var()
        if litnamemap is not None:
            name = litnamemap.get(name, name)
        extra_options = ""
        if show_id:
            extra_options += f",xlabel=\"{vtree.position()}\""
        s += [f"{vtree.position()} [label=\"{name}\",shape=\"box\"{extra_options}];"]
    else:
        extra_options = ""
        if show_id:
            extra_options += f",xlabel=\"{vtree.position()}\""
        s += [f"{vtree.position()} [shape=\"point\"{extra_options}];"]
    if left is not None:
        s += [f"{vtree.position()} -> {left.position()} [arrowhead=none];"]
        s += _vtree_to_dot_int(left, litnamemap, show_id)
    if right is not None:
        s += [f"{vtree.position()} -> {right.position()} [arrowhead=none];"]
        s += _vtree_to_dot_int(right, litnamemap, show_id)
    return s


def nnf_file_wmc(nnf_filename, weights=None):
    """Perform non-smoothed Weighted Model Counting on the given NNF file.

    This is an auxiliary function to perform WMC given an NNF file with only
    Python code. This function will thus also work, even if the C SDD library
    is not available.

    A typical NNF file looks like:

    nnf 12 12 3
    L 1
    ...
    A 2 3 9
    O 2 2 2 10

    """
    wmc = []  # type: List[Optional[float]]
    ln = 0
    detected_nnf = False
    true_weight = 1.0
    false_weight = 0.0
    with open(nnf_filename, 'r') as nnf_file:
        for line in nnf_file.readlines():
            cols = line.strip().split(' ')
            if cols[0] == 'c':
                continue
            if cols[0] == 'nnf':
                wmc = [None] * int(cols[1])
                detected_nnf = True
                continue
            if not detected_nnf:
                raise Exception(f"An NNF file should start with 'nnf'")
            if cols[0] == 'L':
                lit = int(cols[1])
                if lit in weights:
                    wmc[ln] = weights[lit]
                else:
                    wmc[ln] = true_weight
            if cols[0] == 'A':
                wmc[ln] = 1.0
                for i in range(int(cols[1])):
                    wmc[ln] *= wmc[int(cols[2 + i])]
            if cols[0] == 'O':
                wmc[ln] = false_weight
                for i in range(int(cols[2])):
                    wmc[ln] += wmc[int(cols[3 + i])]
            ln += 1
    return wmc[-1]


def sdd_file_wmc(sdd_filename, weights=None):
    """Perform non-smoothed Weighted Model Counting on the given SDD file.

    This is an auxiliary function to perform WMC given an SDD file with only
    Python code. This function will thus also work, even if the C SDD library
    is not available.

    A typical SDD file looks like:

    sdd 11
    L 1 0 1
    ...
    D 0 1 2 1 2 7 8
    """
    wmc = []  # type: List[Optional[float]]
    ln = 0
    detected_sdd = False
    true_weight = 1.0
    false_weight = 0.0
    with open(sdd_filename, 'r') as sdd_file:
        for line in sdd_file.readlines():
            cols = line.strip().split(' ')
            if cols[0] == 'c':
                continue
            if cols[0] == 'sdd':
                detected_sdd = True
                wmc = [None] * int(cols[1])
                continue
            if not detected_sdd:
                raise Exception(f"An SDD file should start with 'sdd'")
            if cols[0] == 'L':
                nodeid = int(cols[1])
                lit = int(cols[3])
                if lit in weights:
                    wmc[nodeid] = weights[lit]
                else:
                    wmc[nodeid] = 1.0
            if cols[0] == 'F':
                nodeid = int(cols[1])
                wmc[nodeid] = false_weight
            if cols[0] == 'T':
                nodeid = int(cols[1])
                wmc[nodeid] = true_weight
            if cols[0] == 'D':
                nodeid = int(cols[1])
                nb_elmts = int(cols[3])
                elmts = [int(col) for col in cols[4:]]
                w = 0.0
                for idx in range(nb_elmts):
                    w += wmc[elmts[2 * idx]] * wmc[elmts[2 * idx + 1]]
                wmc[nodeid] = w
            ln += 1
    return wmc[0]
