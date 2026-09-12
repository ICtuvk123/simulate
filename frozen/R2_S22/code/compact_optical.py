"""Certified small optical covers; hypotheses rank orders, never certify them."""
import itertools,math

RADIUS=20-1e-5


def rectangle_covers(poly,max_points=4):
    # Try the long-axis direction and polygon edge directions. Each resulting
    # bounding rectangle is partitioned into cells with diagonal <= 2*RADIUS.
    a,b=max(((a,b) for a in poly for b in poly),key=lambda pair:math.dist(*pair))
    angles=[math.atan2(b[1]-a[1],b[0]-a[0])]
    angles.extend(math.atan2(b[1]-a[1],b[0]-a[0]) for a,b in zip(poly,poly[1:]+poly[:1]) if math.dist(a,b)>1e-7)
    seen=set()
    for angle in angles:
        angle=angle%math.pi;key=round(angle,10)
        if key in seen:continue
        seen.add(key);d=(math.cos(angle),math.sin(angle));n=(-d[1],d[0])
        xs=[sum(p[k]*d[k] for k in (0,1)) for p in poly]
        ys=[sum(p[k]*n[k] for k in (0,1)) for p in poly]
        x0,x1=min(xs)-1e-7,max(xs)+1e-7;y0,y1=min(ys)-1e-7,max(ys)+1e-7
        width=x1-x0;height=y1-y0
        for ny in range(1,max_points+1):
            half_y=height/(2*ny)
            if half_y>=RADIUS:continue
            half_x=math.sqrt(RADIUS**2-half_y**2)
            nx=max(1,math.ceil(width/(2*half_x)))
            if nx*ny>max_points:continue
            points=[]
            for iy in range(ny):
                for ix in range(nx):
                    x=x0+(ix+.5)*width/nx;y=y0+(iy+.5)*height/ny
                    points.append((x*d[0]+y*n[0],x*d[1]+y*n[1]))
            witness=dict(d=d,n=n,bounds=[x0,y0,x1,y1],nx=nx,ny=ny,
                         cell_radius=math.hypot(width/(2*nx),height/(2*ny)),radius=RADIUS,
                         before_polygon=poly)
            if witness['cell_radius']<=RADIUS+1e-10:yield points,witness


def expected_optical_cost(current,points,models,anchor=None):
    expected=0.;failure_mass=0.
    for model in models:
        position=current;cost=0.;done=False
        for q in points:
            cost+=math.dist(position,q)/5+3;position=q
            if math.dist(q,model['g'])<=20:
                cost+=2+(math.dist(q,anchor)/5 if anchor is not None else 0.);done=True;break
            failure_mass+=model['weight']
        if not done:cost+=10000  # Conservative ranking rejection; not a proof.
        expected+=model['weight']*cost
    return expected,failure_mass


def choose_cover(poly,current,models,anchor=None,max_points=4):
    if not models:return None
    best=None
    for points,witness in rectangle_covers(poly,max_points):
        for order in itertools.permutations(points):
            cost,failures=expected_optical_cost(current,order,models,anchor)
            if best is None or cost<best['estimated_remaining_s']:
                best=dict(points=list(order),witness=witness,estimated_remaining_s=cost,
                          predicted_failed_optical_count=failures,assumptions_only_for_ranking=True)
    return best


def verify_cover(witness,points):
    d=witness['d'];n=witness['n'];x0,y0,x1,y1=witness['bounds'];nx=witness['nx'];ny=witness['ny']
    if nx<1 or ny<1 or len(points)!=nx*ny:return False
    if abs(sum(d[k]*n[k] for k in (0,1)))>1e-10:return False
    if abs(math.hypot(*d)-1)>1e-10 or abs(math.hypot(*n)-1)>1e-10:return False
    if not all(x0<=sum(p[k]*d[k] for k in (0,1))<=x1 and y0<=sum(p[k]*n[k] for k in (0,1))<=y1
               for p in witness['before_polygon']):return False
    half=math.hypot((x1-x0)/(2*nx),(y1-y0)/(2*ny))
    if half>RADIUS+1e-10:return False
    wanted=[]
    for iy in range(ny):
        for ix in range(nx):
            x=x0+(ix+.5)*(x1-x0)/nx;y=y0+(iy+.5)*(y1-y0)/ny
            wanted.append((x*d[0]+y*n[0],x*d[1]+y*n[1]))
    return all(any(math.dist(q,p)<=1e-8 for p in points) for q in wanted)
