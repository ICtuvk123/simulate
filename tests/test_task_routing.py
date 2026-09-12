import itertools
import math
import unittest
from task_routing import area_centroid, open_task_route


class TaskRouteTests(unittest.TestCase):
    def test_area_centroid_triangle(self):
        self.assertEqual(area_centroid([(0,0),(9,0),(0,6)]),(3,2))

    def test_directed_exact_matches_permutations(self):
        start=(1,7);entries=[(0,0),(20,3),(-8,4),(7,-8),(3,9)]
        exits=[(8,2),(-10,7),(-4,-5),(6,10),(20,-8)]
        def cost(order):return math.dist(start,entries[order[0]])+sum(math.dist(exits[a],entries[b]) for a,b in zip(order,order[1:]))
        result=open_task_route(start,entries,exits)
        self.assertAlmostEqual(cost(result),min(cost(o) for o in itertools.permutations(range(5))))

    def test_directed_large_beats_initial_greedy(self):
        entries=[(80*math.cos(i),60*math.sin(i)) for i in range(12)]
        exits=[(30*math.sin(i),70*math.cos(i)) for i in range(12)]
        start=(5,20);route=open_task_route(start,entries,exits)
        self.assertEqual(sorted(route),list(range(12)))
        first=min(range(12),key=lambda i:math.dist(start,entries[i]))
        greedy=[first];left=set(range(12))-{first}
        while left:
            nxt=min(left,key=lambda i:math.dist(exits[greedy[-1]],entries[i]));greedy.append(nxt);left.remove(nxt)
        def cost(o):return math.dist(start,entries[o[0]])+sum(math.dist(exits[a],entries[b]) for a,b in zip(o,o[1:]))
        self.assertLessEqual(cost(route),cost(greedy)+1e-8)
