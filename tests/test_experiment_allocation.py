import collections,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from experiment import allocate_tasks

class AllocationTests(unittest.TestCase):
    def test_each_case_once_and_each_variant_balanced(self):
        for count in (1,2,3,30,100,200):
            for variants in (2,3,7):
                tasks=[dict(seed=500000+s,variant=str(v),scene={'x':s}) for s in range(count) for v in range(variants)]
                groups=allocate_tasks(tasks,4)
                self.assertEqual(sorted(i for group in groups for i,_ in group),list(range(len(tasks))))
                for group in groups:
                    self.assertEqual([i for i,_ in group],sorted(i for i,_ in group))
                    for i,t in group:self.assertIs(t,tasks[i])
                for v in range(variants):
                    counts=[sum(t['variant']==str(v) for _,t in group) for group in groups]
                    self.assertLessEqual(max(counts)-min(counts),1)

    def test_empty_and_invalid(self):
        self.assertEqual(allocate_tasks([],4),[[],[],[],[]])
        with self.assertRaises(ValueError):allocate_tasks([],0)

if __name__=='__main__':unittest.main()
