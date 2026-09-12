"""Directed open route over legal-history estimates of task entry and exit.

These coordinates rank future tasks only. No forecast enters a certificate.
"""
import math


def area_centroid(poly):
    pairs=list(zip(poly,poly[1:]+poly[:1]))
    weights=[a[0]*b[1]-b[0]*a[1] for a,b in pairs]
    area2=sum(weights)
    if abs(area2)<1e-12:
        return tuple(sum(p[k] for p in poly)/len(poly) for k in (0,1))
    return tuple(sum((a[k]+b[k])*w for (a,b),w in zip(pairs,weights))/(3*area2) for k in (0,1))


def open_task_route(start, entries, exits):
    n=len(entries)
    if not n:return []
    initial=[math.dist(start,p) for p in entries]
    edges=[[math.dist(a,b) for b in entries] for a in exits]
    def cost(order):
        return initial[order[0]]+sum(edges[a][b] for a,b in zip(order,order[1:]))
    if n<=9:
        dp={(1<<i,i):(initial[i],(i,)) for i in range(n)}
        for mask in range(1,1<<n):
            for last in range(n):
                item=dp.get((mask,last))
                if item is None:continue
                for nxt in range(n):
                    if mask&(1<<nxt):continue
                    key=(mask|(1<<nxt),nxt)
                    value=(item[0]+edges[last][nxt],item[1]+(nxt,))
                    if key not in dp or value<dp[key]:dp[key]=value
        return list(min(dp[((1<<n)-1,i)] for i in range(n))[1])
    best=None
    for first in sorted(range(n),key=lambda i:(initial[i],i))[:5]:
        order=[first];left=set(range(n))-{first}
        while left:
            nxt=min(left,key=lambda j:(edges[order[-1]][j],j))
            order.append(nxt);left.remove(nxt)
        for _ in range(30):
            # Reversing a directed segment changes every interior edge.
            reverse=[0.]
            for a,b in zip(order,order[1:]):reverse.append(reverse[-1]+edges[b][a]-edges[a][b])
            improvement=1e-6;chosen=None
            for i in range(n-1):
                for j in range(i+1,n):
                    old=initial[order[i]] if i==0 else edges[order[i-1]][order[i]]
                    new=initial[order[j]] if i==0 else edges[order[i-1]][order[j]]
                    if j+1<n:
                        old+=edges[order[j]][order[j+1]]
                        new+=edges[order[i]][order[j+1]]
                    gain=old-new-(reverse[j]-reverse[i])
                    if gain>improvement:improvement=gain;chosen=(i,j)
            if chosen is None:break
            i,j=chosen;order[i:j+1]=reversed(order[i:j+1])
        value=(cost(order),order)
        if best is None or value<best:best=value
    return best[1]
