import logging
import re
import uuid

import elements_splitter
import repetition_applicator
from state_machine import Edge, State, StateMachine, START_STATE, FINAL_STATE, CHARACTER_CATEGORIES

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ParseTree():

    def __init__(self, id_):
        self.id = id_

def parse_from_string(choice_string):
    lines = choice_string.split('\n')

    # Drop empty lines and comments
    lines = [line.strip().split(';')[0] for line in lines if line.strip()]

    machines = {} # {automata_id:string: automata:StateMachine}
    submachines_needed = {} # {automata_id:string: [automata_id:string]}

    for line in lines:
        rulename, elements = line.split('=', 1)
        rulename = rulename.strip()
        machine, submachines_needed = parse_elements(rulename, elements)
        machines[machine.id] = machine
        submachines_needed[machine.id] = submachines_needed

# Returns machine: StateMachine
def parse_elements(rulename, elements):
    machine = StateMachine(rulename)
    machine_start = State(START_STATE)
    machine_end = State(FINAL_STATE)

    elements = elements_splitter.split_into_tokens(elements)
    start_edges, end_states, states = recursive_parse_elements(elements)

    for state in states:
        machine.add_state(state)
    for start_edge in start_edges:
        machine_start.add_edge(start_edge)
    for end_state in end_states:
        machine_end.add_edge('', state.id)

    machine.add_state(machine_start)
    machine.add_state(machine_end)

    return machine

# Returns start_edges: [Edge], end_states: [State], states: [State]
def recursive_parse_elements(elements, used_state_ids=None):
    logger.debug('Parsing elements {elements}')
    current_states = []
    next_states = []
    start_edges = []
    end_states = []
    states = []

    current_end_states = []
    new_states = []
    new_end_states = []
    in_edges = []

    if used_state_ids == None:
        used_state_ids = {} # {state_id:string: times_used:int}
    first_iteration = True

    i = 0
    while i < len(elements):
        logger.debug(f'i: {i} | {elements[i:]}')
        tokens, i = get_concurrent_tokens(elements, i)
        logger.debug(f'Tokens: {tokens}')

        for token in tokens:
            logger.debug(f'Processing token "{token}"')
            token, repetition = get_repetition(token)
            logger.debug(f'Got repetition. token: "{token}", repetition: {repetition}')
            token, is_optional = get_optionality(token)
            logger.debug(f'Got optionality. token: "{token}", is_optional: {is_optional}')

            # If we have a group, we have to recurse down into it, because the internal
            # structure of these states could be anything.
            if isinstance(token, list):
                logger.debug(f'Token "{token}" is list, recursing.')
                in_edges, new_end_states, new_states = recursive_parse_elements(token, used_state_ids)

            else:
                token, is_automata = is_automata_token(token)

                # Make sure the token hasn't been used before. If it has, then we
                # need to add a suffix onto it.
                # TODO: Make sure state machines know to ignore this suffix, or find
                # a better way to register which state machine goes with which token.
                if token in used_state_ids:
                    unique_token = token + f'_#{used_state_ids[token]+1}'
                    logger.debug(f'Token "{token}" is already in use. Changing to {unique_token}.')
                    used_state_ids[token] += 1
                else:
                    unique_token = token
                    used_state_ids[token] = 1

                new_state = State(unique_token, is_automata = is_automata)
                new_end_states = [new_state]
                new_states = [new_state]


                in_edge = Edge(token, new_state.id)
                in_edges = [in_edge]


            in_edges, new_end_states, new_states = repetition_applicator.apply_repetition(in_edges, new_end_states, new_states, repetition, is_optional)
            logger.debug(f'Got multi_apply_repetition result of {in_edges, new_end_states, new_states}.')

            if first_iteration:
                logger.debug(f'Appending edge {in_edges} start_edges.')
                start_edges += in_edges
            else:
                for current_state in current_end_states:
                    for edge in in_edges:
                        logger.debug(f'Appending edge {edge} to current_end_states {current_state.id}.')
                        current_state.add_edge(in_edge)
            states += new_states
        # End for token in tokens loop
        first_iteration = False
        logger.debug(f'Reached end of concurrent tokens, setting current_states to next_states.')
        current_end_states = new_end_states
    # End i < len(elements) loop
    end_states = current_end_states

    logger.debug(f'Returning {(start_edges, end_states, states)}.')
    return start_edges, end_states, states

def is_automata_token(token):
    is_character_class = token in CHARACTER_CATEGORIES.keys()
    quoted_string = False
    if is_quoted_string(token):
        quoted_string = True
        token = dequote_string(token)
    is_automata = not quoted_string and not is_character_class
    return token, is_automata

def get_concurrent_tokens(elements, i):
    concurrent_elements = []
    concurrent_elements.append(elements[i])
    while i+1 < len(elements) and elements[i+1] == '/':
        assert i+2 < len(elements), f'Got a "/" with nothing following it in "{elements}"!'
        i += 2
        concurrent_elements.append(elements[i])
    i += 1
    return concurrent_elements, i

def get_repetition(element):
    if not isinstance(element, list):
        return element, None
    min_reps = 0
    max_reps = float('inf')
    match = re.fullmatch('(\d*)?\*(\d*)|(\d+)?', element[0])
    if match:
        if match.group(1):
            min_reps = int(match.group(1))
        if match.group(2):
            max_reps = int(match.group(2))
        if match.group(3):
            min_reps = max_reps = int(match.group(3))
        return element[1], (min_reps, max_reps)
    else:
        return element, None

def get_optionality(element):
    if not isinstance(element, list):
        return element, False
    if element[0] == '[' and element[-1] == ']':
        unbracketed_element = element[1:-1]
        if len(unbracketed_element) == 1:
            unbracketed_element = unbracketed_element[0]
        return unbracketed_element, True
    else:
        return element, False

def is_quoted_string(string):
    return string[0] == '"' and string[-1] == '"'

def dequote_string(string):
    return string[1:-1]

# if __name__ == '__main__':
#     args = set_up_logging.set_up_logging()
