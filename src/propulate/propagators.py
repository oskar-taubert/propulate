import random
import copy

from.population import Individual

# TODO add crossover
# TODO add simplex step?

def _check_compatible(out1, in2):
    return out1 == in2 or in2==-1


class Propagator():
    """
    A Propagator takes a collection of individuals and uses them to breed a new collection of individuals.
    """
    def __init__(self, parents=0, offspring=0):
        """
        parents: number of input individuals. -1 for any
        offspring: number of output individuals
        """
        self.parents = parents
        self.offspring = offspring
        if offspring == 0:
            raise ValueError("Propagator has to sire more than 0 offspring.")
        return
    def __call__(self, inds):
        raise NotImplementedError()


class Stochastic(Propagator):
    """
    A StochasticPropagator is only applied with a given probability.
    If it is not applied the output still has to adhere to the defined number of offspring.
    """
    def __init__(self, parents=0, offspring=0, probability=1.):
        """
        parents: number of input individuals. -1 for any
        offspring: number of output individuals
        probability: probability of applying the propagator
        """
        super(Stochastic, self).__init__(parents, offspring)
        self.probability = probability
        if offspring == 0:
            raise ValueError("Propagator has to sire more than 0 offspring.")
        return
    def __call__(self, inds):
        raise NotImplementedError()
        return


# TODO this turned not quite out like i imagined. if the user defines a conditional function, i have to ship that over mpi
# TODO so for now it's the one condition i want to have now and for the rest we'll wait for feedback
class Conditional(Propagator):
    """
    """
    def __init__(self, pop_size, true_prop, false_prop, parents=-1, offspring=-1):
        """
        condition: callable, if it returns True when called with input to call, true_prop is applied, false_prop otherwise.
        """
        super(Conditional, self).__init__(parents, offspring)
        self.pop_size = pop_size
        self.true_prop = true_prop
        self.false_prop = false_prop

    def __call__(self, inds):
        if len(inds) >= self.pop_size:
            return self.true_prop(inds)
        else:
            return self.false_prop(inds)


class Cascade(Propagator):
    def __init__(self, propagators):
        super(Cascade, self).__init__(propagators[0].parents, propagators[-1].offspring)
        self.propagators = propagators
        for i in range(len(propagators)-1):
            if not _check_compatible(propagators[i].offspring, propagators[i+1].parents):
                outp = propagators[i]
                inp = propagators[i+1]
                outd = outp.offspring
                ind = indp.parents

                raise ValueError("Incompatible combination of {} output individuals of {} and {} input individuals of {}".format(outd, outp, ind, inp))

    def __call__(self, inds):
        for p in self.propagators:
            inds = p(inds)
        return inds


# TODO random number of points to mutate
class PointMutation(Stochastic):
    def __init__(self, limits, points=1, probability=1.):
        super(PointMutation, self).__init__(1, 1, probability)
        self.points = points
        self.limits = limits
        if len(limits) < points:
            raise ValueError("Too many points to mutate for individual with {} traits".format(len(limits)))
        return

    def __call__(self, ind):
        if random.random() < self.probability:
            ind = copy.deepcopy(ind)
            ind.loss = None
            to_mutate = random.sample(ind.keys(), self.points)
            for i in to_mutate:
                if type(ind[i]) == int:
                    ind[i] = random.randrange(*self.limits[i])
                elif type(ind[i]) == float:
                    ind[i] = random.uniform(*self.limits[i])
                elif type(ind[i]) == str:
                    ind[i] = random.choice(self.limits[i])

        return ind


# TODO rename to IntervalMutationClampedRelativeNormal? Or do this all in parameters if mu is set absolute and so on
class IntervalMutationNormal(Stochastic):
    def __init__(self, limits, sigma_factor=.1, points=1, probability=1.):
        super(IntervalMutationNormal, self).__init__(1, 1, probability)
        self.points = points
        self.limits = limits
        self.sigma_factor = sigma_factor
        n_interval_traits = len([x for x in limits if type(limits[x][0]) == float])
        if n_interval_traits < points:
            raise ValueError("Too many points to mutate for individual with {} interval traits".format(n_interval_traits))
        return

    def __call__(self, ind):
        if random.random() < self.probability:
            ind = copy.deepcopy(ind)
            ind.loss = None
            interval_keys = [x for x in ind.keys() if type(ind[x])==float]
            to_mutate = random.sample(interval_keys, self.points)
            for i in to_mutate:
                min_val, max_val = self.limits[i]
                mu = ind[i]
                sigma = (max_val-min_val)*self.sigma_factor
                ind[i] = random.gauss(mu, sigma)
                ind[i] = min(max_val, ind[i])
                ind[i] = max(min_val, ind[i])

        return ind


class MateUniform(Stochastic):
    def __init__(self, probability):
        super(MateUniform, self).__init__(2, 1, probability)
        return
    def __call__(self, inds):
        ind = copy.deepcopy(inds[0])
        if random.random() < self.probability:
            ind.loss = None
            for k in inds[1].keys():
                if random.random() > 0.5:
                    ind[k] = inds[1][k]
        return ind


class SelectBest(Stochastic):
    def __init__(self, offspring):
        super(SelectBest, self).__init__(-1, offspring, 1.)
        return

    def __call__(self, inds):
        if len(inds) < self.offspring:
            raise ValueError("Has to have at least {} individuals to select the {} best ones".format(self.offspring, self.offspring))
        return sorted(inds, key=lambda ind: ind.loss)[:self.offspring]


class SelectUniform(Stochastic):
    def __init__(self, offspring):
        super(SelectUniform, self).__init__(-1, offspring, 1.)
        return

    def __call__(self, inds):
        if len(inds) < self.offspring:
            raise ValueError("Has to have at least {} individuals to select {} from them".format(self.offspring, self.offspring))
        # TODO sorted?
        return random.sample(inds, self.offspring)


# TODO children != 1 case
# TODO parents should be fixed to one NOTE see utils reason why it is not right now
class InitUniform(Stochastic):
    def __init__(self, limits, parents=0, probability=1.):
        """
        In case of parents > 0 and probability < 1., call returns input individual without change
        """
        super(InitUniform, self).__init__(parents, 1, probability)
        self.limits = limits
        return
    def __call__(self, *inds):
        if random.random() < self.probability:
            ind = Individual()
            for limit in self.limits:
                if type(self.limits[limit][0]) == int:
                    ind[limit] = random.randrange(*self.limits[limit])
                elif type(self.limits[limit][0]) == float:
                    ind[limit] = random.uniform(*self.limits[limit])
                elif type(self.limits[limit][0]) == str:
                    ind[limit] = random.choice(self.limits[limit])
                else:
                    raise ValueError("Unknown type of limits. Has to be float for interval, int for ordinal, or string for categorical.")
            return ind
        else :
            ind = inds[0]
            return ind
