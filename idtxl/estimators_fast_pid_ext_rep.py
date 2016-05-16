import sys
import numpy as np

import jpype as jp

def pid(s1, s2, t, cfg):
    """Provide a fast implementation of the PDI estimator for discrete data.

This module exports a fast implementation of the partial information
decomposition (PID) estimator for discrete data. The estimator does not require
JAVA or GPU modules to run.

Improved version with larger initial swaps and checking for convergence of both
the unique information from sources 1 and 2.
    """

    if s1.ndim != 1 or s2.ndim != 1 or t.ndim != 1:
        raise ValueError('Inputs s1, s2, target have to be vectors'
                         '(1D-arrays).')
    if (len(t) != len(s1) or len(t) != len(s2)):
        raise ValueError('Number of samples s1, s2 and t must be equal')

    try:
        alph_s1 = cfg['alph_s1']
    except TypeError:
        print('The cfg argument should be a dictionary.')
        raise
    except KeyError:
        print('"alph_s1" is missing from the cfg dictionary.')
        raise
    try:
        alph_s2 = cfg['alph_s2']
    except KeyError:
        print('"alph_s2" is missing from the cfg dictionary.')
        raise
    try:
        alph_t = cfg['alph_t']
    except KeyError:
        print('"alph_t" is missing from the cfg dictionary.')
        raise
    try:
        max_unsuc_swaps_row_parm = cfg['max_unsuc_swaps_row_parm']
    except KeyError:
        print('"max_unsuc_swaps_row_parm" is missing from the cfg dictionary.')
        raise
    try:
        num_reps = cfg['num_reps']
    except KeyError:
        print('"num_reps" is missing from the cfg dictionary.')
        raise
    if (num_reps > 63):
        raise ValueError('Number of reps must be 63 or less to prevent integer overflow')
    try:
        max_iters = cfg['max_iters']
    except KeyError:
        print('"max_iters" is missing from the cfg dictionary.')
        raise
    
    # -- DEFINE PARAMETERS -- #

    num_samples = len(t)

    # Max swaps = number of possible swaps * control parameter
    num_pos_swaps = alph_t * alph_s1 * (alph_s1-1) * alph_s2 * (alph_s2-1)
    max_unsuc_swaps_row = np.floor(num_pos_swaps * max_unsuc_swaps_row_parm)

    # -- CALCULATE PROBABLITIES -- #

    # Declare arrays for counts
    t_count = np.zeros(alph_t, dtype=np.int)
    s1_count = np.zeros(alph_s1, dtype=np.int)
    s2_count = np.zeros(alph_s2, dtype=np.int)
    joint_t_s1_count = np.zeros((alph_t, alph_s1), dtype=np.int)
    joint_t_s2_count = np.zeros((alph_t, alph_s2), dtype=np.int)
    joint_s1_s2_count = np.zeros((alph_s1, alph_s2), dtype=np.int)
    joint_t_s1_s2_count = np.zeros((alph_t, alph_s1, alph_s2),
                                   dtype=np.int)

    # Count observations
    for obs in range(0, num_samples):
        t_count[t[obs]] += 1
        s1_count[s1[obs]] += 1
        s2_count[s2[obs]] += 1
        joint_t_s1_count[t[obs], s1[obs]] += 1
        joint_t_s2_count[t[obs], s2[obs]] += 1
        joint_s1_s2_count[s1[obs], s2[obs]] +=1
        joint_t_s1_s2_count[t[obs], s1[obs], s2[obs]] += 1
#    min_joint_nonzero_count = np.min(
#				np.min(
#				np.min(
#				joint_t_s1_s2_count[np.nonzero(joint_t_s1_s2_count)])))

    max_joint_nonzero_count = np.max(joint_t_s1_s2_count[np.nonzero(joint_t_s1_s2_count)])


    # Fixed probabilities
    t_prob = np.divide(t_count, num_samples).astype('float128')
    s1_prob = np.divide(s1_count, num_samples).astype('float128')
    s2_prob = np.divide(s2_count, num_samples).astype('float128')
    joint_t_s1_prob = np.divide(joint_t_s1_count, num_samples).astype('float128')
    joint_t_s2_prob = np.divide(joint_t_s2_count, num_samples).astype('float128')

    # Variable probabilities
    joint_s1_s2_prob = np.divide(joint_s1_s2_count, num_samples).astype('float128')
    joint_t_s1_s2_prob = np.divide(joint_t_s1_s2_count, num_samples).astype('float128')
    max_prob = np.max(joint_t_s1_s2_prob[np.nonzero(joint_t_s1_s2_prob)])

#    # make copies of the variable probabilities for independent second
#    # optimization and comparison of KLDs for convergence check:
#    # KLDs should initially rise and then fall when close to the minimum
#    joint_s1_s2_prob_alt = joint_s1_s2_prob.copy()
#    joint_t_s1_s2_prob_alt = joint_t_s1_s2_prob.copy()


    # JIDT IS BACK

    jarpath = '/home/conor/projects/idtxl/git/IDTxl/idtxl/infodynamics.jar'
    
    if not jp.isJVMStarted():
        jp.startJVM(jp.getDefaultJVMPath(),
                    '-ea', '-Djava.class.path=' + jarpath)

    Cmi_calc_class = (jp.JPackage('infodynamics.measures.discrete')
                      .ConditionalMutualInformationCalculatorDiscrete)
    Mi_calc_class = (jp.JPackage('infodynamics.measures.discrete')
                     .MutualInformationCalculatorDiscrete)

    cmi_calc_t_s1_cond_s2 = Cmi_calc_class(alph_t,alph_s1,alph_s2)
    cmi_calc_t_s2_cond_s1 = Cmi_calc_class(alph_t,alph_s2,alph_s1)
    cmi_t_s1_cond_s2 = _calculate_cmi(cmi_calc_t_s1_cond_s2, t, s1, s2)
    cmi_t_s2_cond_s1 = _calculate_cmi(cmi_calc_t_s2_cond_s1, t, s2, s1)

    alph_max = max(alph_s1*alph_s2, alph_t)
    jointmi_calc  = Mi_calc_class(alph_max)
    jointmi_s1s2_t = _calculate_jointmi(jointmi_calc, s1, s2, t)
    
    print('JIDT CMI (s1):\t', cmi_t_s2_cond_s1)    
    print('JIDT CMI (s2):\t', cmi_t_s1_cond_s2)
    print('JIDT JMI:\t', jointmi_s1s2_t)

    
    # -- VIRTUALISED SWAPS -- #

    # Calculate the initial cmi's and store them
    cond_mut_info1 = _cmi_prob(
        s2_prob, joint_t_s2_prob, joint_s1_s2_prob, joint_t_s1_s2_prob)
    cur_cond_mut_info1 = cond_mut_info1

    cond_mut_info2 = _cmi_prob(
        s1_prob, joint_t_s1_prob, joint_s1_s2_prob, joint_t_s1_s2_prob)
    cur_cond_mut_info2 = cond_mut_info2

    # sanity check: the curr cmi must be smaller than the joint, else something
    # is fishy
    #
    jointmi_s1s2_t = _joint_mi(s1, s2, t, alph_s1, alph_s2, alph_t)

    if cond_mut_info1 > jointmi_s1s2_t:
        raise ValueError('joint MI {0} smaller than cMI {1}'
                         ''.format(jointmi_s1s2_t, cond_mut_info1))
    else:
        print('Passed sanity check on jMI and cMI')


    # Declare reps array of repeated doubling to half the prob_inc
    # WARNING: num_reps greater than 63 results in integer overflow
    # TODO: in principle we could divide the increment until we run out of fp
    # precision, e.g.
    # we can get some extra reps by not starting with a swap of size 1/n
    # but soemthing larger, by adding as many steps here as we are powers of 2
    # larger in the max probability than 1/n
    # and by starting with swaps in the size of the max probability
    # this will keep almost all of the bins of the joint pdf from being swapped
    # but they will joint swapping later, or after being swapped into
    # unfortunatley this does not run with the current code as it uses large
    # powers of integers
    # another idea would be to decrement by something slightly smaller than 2
#    num_reps = num_reps + np.int32(np.floor(np.log(max_joint_nonzero_count)/np.log(2)))
    print("num_reps:")
    print(num_reps)
    reps = np.array(np.power(2,range(0,num_reps)))

    # Replication loop
    for rep in reps:
        prob_inc = np.multiply(
            np.float128(max_prob),
            np.divide(np.float128(1),np.float128(rep)))
        # Want to store number of succesive unsuccessful swaps
        unsuccessful_swaps_row = 0
        # SWAP LOOP
        for attempt_swap in range(0, max_iters):
            # Pick a random candidate from the targets
            t_cand = np.random.randint(0, alph_t)
            s1_cand = np.random.randint(0, alph_s1)
            s2_cand = np.random.randint(0, alph_s2)

            # Pick a swap candidate
            s1_prim = np.random.randint(0, alph_s1-1)
            if (s1_prim >= s1_cand):
                s1_prim += 1
            s2_prim = np.random.randint(0, alph_s2-1)
            if (s2_prim >= s2_cand):
                s2_prim += 1

#            unsuccessful_swaps_row = _try_swap(cur_cond_mut_info,
#                                               joint_t_s1_s2_prob,
#                                               joint_s1_s2_prob,
#                                               joint_t_s2_prob, s2_prob,
#                                               t_cand, s1_prim, s2_prim,
#                                               s1_cand, s2_cand,
#                                               prob_inc,
#                                               unsuccessful_swaps_row)
#            print("unsuccessful_swaps_row: {0}".format(unsuccessful_swaps_row))

            # START of a possible try_swap function
            # based on a fixed set of candidates
            # that can then be used recursively until the swap direction
            # becomes unsuccessful

            # Ensure we can decrement without introducing neg probs
            # this is very important as we start swaps in the size of the
            # maximum probability
            if (joint_t_s1_s2_prob[t_cand, s1_cand, s2_cand] >= prob_inc
                and joint_t_s1_s2_prob[t_cand, s1_prim, s2_prim] >= prob_inc
                and joint_s1_s2_prob[s1_cand, s2_cand] >= prob_inc
                and joint_s1_s2_prob[s1_prim, s2_prim] >= prob_inc):

                joint_t_s1_s2_prob[t_cand, s1_cand, s2_cand] -= prob_inc
                joint_t_s1_s2_prob[t_cand, s1_prim, s2_prim] -= prob_inc
                joint_t_s1_s2_prob[t_cand, s1_cand, s2_prim] += prob_inc
                joint_t_s1_s2_prob[t_cand, s1_prim, s2_cand] += prob_inc

                joint_s1_s2_prob[s1_cand, s2_cand] -= prob_inc
                joint_s1_s2_prob[s1_prim, s2_prim] -= prob_inc
                joint_s1_s2_prob[s1_cand, s2_prim] += prob_inc
                joint_s1_s2_prob[s1_prim, s2_cand] += prob_inc

                # Calculate the cmi after this virtual swap
                cond_mut_info1 = _cmi_prob(
                    s2_prob, joint_t_s2_prob, joint_s1_s2_prob, joint_t_s1_s2_prob)
                cond_mut_info2 = _cmi_prob(
                    s2_prob, joint_t_s2_prob, joint_s1_s2_prob, joint_t_s1_s2_prob)

                # If at least one of the cmis is improved keep it,
                # reset the unsuccessful swap counter
                if ( cond_mut_info1 < cur_cond_mut_info1 or
                     cond_mut_info2 < cur_cond_mut_info2):
                    cur_cond_mut_info1 = cond_mut_info1
                    cur_cond_mut_info2 = cond_mut_info2
                    unsuccessful_swaps_row = 0
                    # TODO: if this swap direction was successful - repeat it !
                # Else undo the changes, record unsuccessful swap
                else:
                    joint_t_s1_s2_prob[t_cand, s1_cand, s2_cand] += prob_inc
                    joint_t_s1_s2_prob[t_cand, s1_prim, s2_prim] += prob_inc
                    joint_t_s1_s2_prob[t_cand, s1_cand, s2_prim] -= prob_inc
                    joint_t_s1_s2_prob[t_cand, s1_prim, s2_cand] -= prob_inc

                    joint_s1_s2_prob[s1_cand, s2_cand] += prob_inc
                    joint_s1_s2_prob[s1_prim, s2_prim] += prob_inc
                    joint_s1_s2_prob[s1_cand, s2_prim] -= prob_inc
                    joint_s1_s2_prob[s1_prim, s2_cand] -= prob_inc

                    unsuccessful_swaps_row += 1
            else:
                unsuccessful_swaps_row += 1
            # END of a possible try_swap function

            if (unsuccessful_swaps_row >= max_unsuc_swaps_row):
                break

    # print(cond_mut_info, '\t', prob_inc, '\t', unsuccessful_swaps_row)

    # -- PID Evaluation -- #

    # Classical mutual information terms
    mi_target_s1 = _mi_prob(t_prob, s1_prob, joint_t_s1_prob)
    mi_target_s2 = _mi_prob(t_prob, s2_prob, joint_t_s2_prob)
    jointmi_s1s2_target = _joint_mi(s1, s2, t, alph_s1, alph_s2, alph_t)
    print('jointmi_s1s2_target: {0}'.format(jointmi_s1s2_target))

    # PID terms
    unq_s1 = cond_mut_info1
    shd_s1_s2 = mi_target_s1 - unq_s1
    unq_s2 = mi_target_s2 - shd_s1_s2
    syn_s1_s2 = jointmi_s1s2_target - unq_s1 - unq_s2 - shd_s1_s2

    estimate = {
        'joint_mi_s1s2_t': jointmi_s1s2_target,
        'unq_s1': unq_s1,
        'unq_s2': unq_s2,
        'shd_s1_s2': shd_s1_s2,
        'syn_s1_s2': syn_s1_s2,
    }

    return estimate




def _cmi_prob(s2cond_prob, joint_t_s2cond_prob,
             joint_s1_s2cond_prob, joint_t_s1_s2cond_prob):

    total = np.zeros(1).astype('float128')

    [alph_t, alph_s1, alph_s2cond] = np.shape(joint_t_s1_s2cond_prob)

    for sym_s1 in range(0, alph_s1):
        for sym_s2cond in range(0, alph_s2cond):
            for sym_t in range(0, alph_t):

                if ( s2cond_prob[sym_s2cond]
                     * joint_t_s2cond_prob[sym_t, sym_s2cond]
                     * joint_s1_s2cond_prob[sym_s1, sym_s2cond]
                     * joint_t_s1_s2cond_prob[sym_t, sym_s1, sym_s2cond] > 0 ):

                    local_contrib = (
                        np.log(joint_t_s1_s2cond_prob[sym_t, sym_s1, sym_s2cond])
                        + np.log(s2cond_prob[sym_s2cond])
                        - np.log(joint_t_s2cond_prob[sym_t,sym_s2cond])
                        - np.log(joint_s1_s2cond_prob[sym_s1, sym_s2cond])
                        ) / np.log(2)

                    weighted_contrib = (
                        joint_t_s1_s2cond_prob[sym_t, sym_s1, sym_s2cond]
                        * local_contrib)
                else:
                    weighted_contrib = 0
                total += weighted_contrib

    return total


def _mi_prob(s1_prob, s2_prob, joint_s1_s2_prob):
    """
    MI calculator in the prob domain
    """
    total = np.zeros(1).astype('float128')

    [alph_s1, alph_s2] = np.shape(joint_s1_s2_prob)

    for sym_s1 in range(0, alph_s1):
        for sym_s2 in range(0, alph_s2):

            if ( s1_prob[sym_s1] * s2_prob[sym_s2]
                 * joint_s1_s2_prob[sym_s1, sym_s2] > 0 ):

                local_contrib = (
                    np.log(joint_s1_s2_prob[sym_s1, sym_s2])
                    - np.log(s1_prob[sym_s1])
                    - np.log(s2_prob[sym_s2])
                    ) / np.log(2)

                weighted_contrib = (
                    joint_s1_s2_prob[sym_s1, sym_s2]
                    * local_contrib)
            else:
                weighted_contrib = 0
            total += weighted_contrib

    return total


def _joint_mi(s1, s2, t, alph_s1, alph_s2, alph_t):
    """
    Joint MI calculator in the samples domain
    """

    [s12, alph_s12] = _join_variables(s1, s2, alph_s1, alph_s2)

    t_count = np.zeros(alph_t, dtype=np.int)
    s12_count = np.zeros(alph_s12, dtype=np.int)
    joint_t_s12_count = np.zeros((alph_t, alph_s12), dtype=np.int)

    num_samples = len(t)

    for obs in range(0, num_samples):
        t_count[t[obs]] += 1
        s12_count[s12[obs]] += 1
        joint_t_s12_count[t[obs], s12[obs]] += 1

    t_prob = np.divide(t_count, num_samples).astype('float128')
    s12_prob = np.divide(s12_count, num_samples).astype('float128')
    joint_t_s12_prob = np.divide(joint_t_s12_count, num_samples).astype('float128')

    jmi = _mi_prob(t_prob, s12_prob, joint_t_s12_prob)

    return jmi


def _join_variables(a, b, alph_a, alph_b):
    """Join two sequences of random variables (RV) into a new RV.

    Works like the method 'computeCombinedValues' implemented in JIDT
    (https://github.com/jlizier/jidt/blob/master/java/source/
    infodynamics/utils/MatrixUtils.java).

    Args:
        a, b (np array): sequence of integer numbers of arbitrary base
            (representing observations from two RVs)
        alph_a, alph_b (int): alphabet size of a and b

    Returns:
        np array, int: joined RV
        int: alphabet size of new RV
    """
    if a.shape[0] != b.shape[0]:
        raise Error

    if alph_b < alph_a:
        a, b = b, a
        alph_a, alph_b = alph_b, alph_a

    joined = np.zeros(a.shape[0])

    for i in range(joined.shape[0]):
        mult = 1
        joined[i] += mult * b[i]
        mult *= alph_a
        joined[i] += mult * a[i]

    alph_new = max(a) * alph_a + alph_b
    '''
    for (int r = 0; r < rows; r++) {
        // For each row in vec1
        int combinedRowValue = 0;
        int multiplier = 1;
        for (int c = columns - 1; c >= 0; c--) {
            // Add in the contribution from each column
            combinedRowValue += separateValues[r][c] * multiplier;
            multiplier *= base;
        }
        combinedValues[r] = combinedRowValue;
    } '''

    return joined.astype(int), alph_new




def _calculate_cmi(cmi_calc, var_1, var_2, cond):
    """Calculate conditional MI from three variables usind JIDT.

    Args:
        cmi_calc (JIDT calculator object): JIDT calculator for conditio-
            nal mutual information
        var_1, var_2 (1D numpy array): realizations of two discrete
            random variables
        cond (1D numpy array): realizations of a discrete random
            variable for conditioning

    Returns:
        double: conditional mutual information between var_1 and var_2
            conditional on cond
    """
    var_1_java = jp.JArray(jp.JInt, var_1.ndim)(var_1.tolist())
    var_2_java = jp.JArray(jp.JInt, var_2.ndim)(var_2.tolist())
    cond_java = jp.JArray(jp.JInt, cond.ndim)(cond.tolist())
    cmi_calc.initialise()
    cmi_calc.addObservations(var_1_java, var_2_java, cond_java)
    cmi = cmi_calc.computeAverageLocalOfObservations()
    return cmi

def _calculate_jointmi(jointmi_calc, s1, s2, target):
    """Calculate MI from three variables usind JIDT.

    Args:
        jointmi_calc (JIDT calculator object): JIDT calculator for
            mutual information
        var_1, var_2, var_3 (1D numpy array): realizations of some
            discrete random variables

    Returns:
        double: mutual information between all three input variables
    """
    mUtils = jp.JPackage('infodynamics.utils').MatrixUtils
    # speed critical line ?
    s12 = mUtils.computeCombinedValues(jp.JArray(jp.JInt, 2)(np.column_stack((s1, s2)).tolist()), 2)
#    [s12, alph_joined] = _join_variables(s1, s2, 2, 2)
    jointmi_calc.initialise()
#    jointmi_calc.addObservations(jp.JArray(jp.JInt, s12.T.ndim)(s12.T.tolist()),
#                                 jp.JArray(jp.JInt, target.ndim)(target.tolist()))
    jointmi_calc.addObservations(s12,jp.JArray(jp.JInt, target.ndim)(target.tolist()))

    jointmi = jointmi_calc.computeAverageLocalOfObservations()
    return jointmi




# TODO fix this - no idea why it does not yield the correct results
#def _try_swap(cur_cond_mut_info, joint_t_s1_s2_prob, joint_s1_s2_prob,
#              joint_t_s2_prob, s2_prob,
#              t_cand, s1_prim, s2_prim, s1_cand, s2_cand,
#              prob_inc, unsuccessful_swaps_row):
##            unsuccessful_swaps_row_local = unsuccessful_swaps_row
##            print("unsuccessful_swaps_row_local: {0}".format(unsuccessful_swaps_row_local))
#            if (joint_t_s1_s2_prob[t_cand, s1_cand, s2_cand] >= prob_inc
#            and joint_t_s1_s2_prob[t_cand, s1_prim, s2_prim] >= prob_inc
#            and joint_s1_s2_prob[s1_cand, s2_cand] >= prob_inc
#            and joint_s1_s2_prob[s1_prim, s2_prim] >= prob_inc):
#
#                joint_t_s1_s2_prob[t_cand, s1_cand, s2_cand] -= prob_inc
#                joint_t_s1_s2_prob[t_cand, s1_prim, s2_prim] -= prob_inc
#                joint_t_s1_s2_prob[t_cand, s1_cand, s2_prim] += prob_inc
#                joint_t_s1_s2_prob[t_cand, s1_prim, s2_cand] += prob_inc
#
#                joint_s1_s2_prob[s1_cand, s2_cand] -= prob_inc
#                joint_s1_s2_prob[s1_prim, s2_prim] -= prob_inc
#                joint_s1_s2_prob[s1_cand, s2_prim] += prob_inc
#                joint_s1_s2_prob[s1_prim, s2_cand] += prob_inc
#
#                # Calculate the cmi after this virtual swap
#                cond_mut_info = _cmi_prob(
#                    s2_prob, joint_t_s2_prob, joint_s1_s2_prob, joint_t_s1_s2_prob)
#
#                # If improved keep it, reset the unsuccessful swap counter
#                if ( cond_mut_info < cur_cond_mut_info ):
#                    cur_cond_mut_info = cond_mut_info
#                    unsuccessful_swaps_row = 0
#                    # TODO: if this swap direction was successful - repeat it !
#                # Else undo the changes, record unsuccessful swap
#                else:
#                    joint_t_s1_s2_prob[t_cand, s1_cand, s2_cand] += prob_inc
#                    joint_t_s1_s2_prob[t_cand, s1_prim, s2_prim] += prob_inc
#                    joint_t_s1_s2_prob[t_cand, s1_cand, s2_prim] -= prob_inc
#                    joint_t_s1_s2_prob[t_cand, s1_prim, s2_cand] -= prob_inc
#
#                    joint_s1_s2_prob[s1_cand, s2_cand] += prob_inc
#                    joint_s1_s2_prob[s1_prim, s2_prim] += prob_inc
#                    joint_s1_s2_prob[s1_cand, s2_prim] -= prob_inc
#                    joint_s1_s2_prob[s1_prim, s2_cand] -= prob_inc
#
#                    unsuccessful_swaps_row += 1
#            else:
#                unsuccessful_swaps_row += 1
#            return unsuccessful_swaps_row # need to return this to make it visible outside
#        # END of a possible try_swap function


