# Topology-Aware Bank Clearing: Mathematical Formulation, Heuristic Collapse on Real Financial Flows, and Exact Large-Scale Optimization

**Author:** Andrea A (24BCE1142)  
**Affiliation:** Department of Computer Science and Engineering, VIT Chennai  
**Course/Date:** Design and Analysis of Algorithms, academic year 2026–2027

---

## Abstract

The Bank Clearing Problem (BCP) consists in selecting a subset of payment obligations to settle from a pool such that the total cleared volume is maximized subject to per-institution deposit limits under multilateral netting. While BCP is NP-hard, prior studies have predominantly evaluated algorithms on small synthetic topologies or toy models (n <= 37). In this paper, we conduct an extensive theoretical and empirical investigation bridging topology-aware decomposition heuristics with exact mixed-integer programming (MIP) on both synthetic scale-free networks and large-scale real-world financial flows from the Stanford SNAP Stablecoin ERC-20 dataset ($1.03 Billion gross volume, 13,308 accounts, 16,093 obligations across USDT, USDC, and DAI).

We first formulate and evaluate the Hub-Spoke Clearing (HSC) decomposition heuristic, which confines exact 0/1 integer optimization to a high-degree core while greedily clearing peripheral super-spokes, backed by a deterministic worklist repair algorithm guaranteeing 100% deposit feasibility. On synthetic scale-free networks (n = 10 to 1,000), HSC captures 90–92% of the optimum (+2.3 to +3.6 pp over greedy). However, when evaluated on real-world financial transaction flows with heavy-tailed payment distributions ($10 to $10M per obligation), standard heuristics experience a catastrophic collapse: Greedy with 1-opt Local Search captures only 34.0% to 51.3% of the optimal volume under liquidity stress (alpha <= 0.20), failing to identify critical clearing cycles. In contrast, exact branch-and-cut via modern HiGHS solves the entire $1.03B network to provable global optimality in 5.40 seconds, clearing nearly double the volume of greedy heuristics. Polyhedral analysis reveals that the continuous LP relaxation integrality gap explodes to 33.2%–52.3% with 30.5%–45.5% fractional variables on real financial networks, explaining the theoretical failure of greedy rounding. Our findings confirm and dramatically extend the 'Just Solve It' paradigm of Cambe and Xing (2024), demonstrating that exact solvers are fully production-viable for real-time gross settlement systems and decentralized clearinghouses at scale.

HSC will always provide a feasible solution that is easy to analyse, outperforms simple greedy and, as long as the hubs are present, is better than pure greedy. In terms of sizes used in the experiment, it cannot compete with other heuristics and the best known algorithm used currently, and hence should be treated as decomposition with analysis rather than a replacement for it.

**Keywords:** bank clearing problem; interbank payment networks; scale-free networks; hub–spoke decomposition; integer programming; heuristic algorithms.

bank clearing problem; interbank payment networks; scale-free networks; hub–spoke decomposition; integer programming; heuristic algorithms.


## 4. Introduction


### 4.1 Background of the Problem

There are many payment orders between banks on a daily basis. Prior to any settlement of payments, mutual debts are netted, and whatever is the amount that the bank needs to pay after the netting is done must have to be backed up by its deposit in the clearing system. In general, the total amount of the payment orders that need to be cleared is always more than the total deposits of the banks. Therefore, not all of the orders can be settled. Rather, only a selection of orders can be chosen, whose objective is to maximize the settlement value without exceeding the deposits of any bank. [1], [2].


### 4.2 Motivation

Real-world networks like Fedwire display a hub-and-spoke structure which exhibits a heavy-tailed distribution; a small number of high-degree banks handle a substantial fraction of links and transactions while the bulk of other banks have low connectivity [4]. Networks of interbank trading in other countries display a comparable core-periphery phenomenon [5]. Standard approaches to BCP do not consider this property. In general, what we are attempting here is that since the difficult portion of combinatorics exists in the core of hubs, the exact technique is only required for the latter while the rest is relatively easy. This paper investigates the validity of this approach.


### 4.3 Importance of the Problem

The clearing center must come up with a clearance in each round within a certain period of time, and such clearing should never exceed the deposit capacity of the bank. The algorithm that does not give a feasible clearance and the one whose time complexity is unbounded is an operational risk. The amount at stake is quite significant, hence the better clearance quality has its value, and the approach which provides a feasible solution within a certain timeframe is attractive.


### 4.4 Limitations of Existing Approaches

Exact ILP (branch-and-cut) gives the true optimum, but its worst-case running time is exponential, and it treats every bank and every arc alike.

Unstructured greedy is fast and simple, but it is myopic. One heavy arc going through a tight bank can block many smaller arcs that are worth more in total somewhere else.

Generic graph partitioning (spectral, METIS-style) produces balanced partitions, which suit meshes but not scale-free graphs, and it comes with no correctness argument for clearing.


### 4.5 Research Objectives

Design a topology-aware decomposition that keeps the exact computation inside a small hub core.

Guarantee that every clearing the method returns is feasible for every bank.

Remove the need to set the hub budget k by hand.

Evaluate the method on synthetic and real networks, including the cases where it does not work, and against baselines strong enough to show whether it is worth using at all.


### 4.6 Main Contributions of the Proposed Work

1. An algorithm (HSC) that partitions banks as hubs and spokes based on their degrees, collapses connected sets of spokes into super-spokes, solves an ILP optimally on the hub-core and divides the output among the real banks, greedily clears the spokes and ends with a repair process.

2. Feasibility proof: the problem of pooled deposits that was there in our first and naïve version, the two-phase fix we have done to it, and the proof that our repair phase always results in a feasible clearing.

3. Approximation factor. The greedy clearing of spokes can be proved to be ½-approximation under a gross-outflow model, but under netting, the greedy clearing has no constant approximation ratio.


#### 4. Adaptive selection of hub budget (select_k_adaptive), along with the explanation of where it fails (n ≥ 500).


#### 6. Real-world financial transaction validation on the Stanford SNAP Stablecoin ERC-20 dataset ($1.03 Billion gross volume, 13,308 nodes, 16,093 arcs), demonstrating that heuristics collapse to 34–51% of optimal under liquidity stress, modern branch-and-cut solves billion-dollar flows in 5.4 seconds, and LP integrality gaps reach 33–52%.


#### 5. Empirical studies on synthetic networks (Barabási–Albert and Erdős–Rényi, n = 10 to 1,000), two real cryptocurrency trust networks (Bitcoin OTC and Bitcoin Alpha, 256 weekly snapshots), and tight-deposit stress sweeps.

The ILP solver and the greedy heuristic remain unchanged and act as subroutines. The contribution is in the decomposition approach, how feasibility is dealt with, and the evaluation method. The approach draws inspiration from the parameterized complexity technique of confining the difficult part within a parameter k [9]; however, the heuristic HSC is not said to be a fixed-parameter tractable algorithm. Neither is the algorithm said to be better than the competing approaches, which turns out to be not true as shown in Section 9.8.


## 5. Literature Review / Related Work


### 5.1 Review of Existing Methods

Güntzer, Jungnickel, and Leclerc [1] established the NP-hardness of the BCP on national interbank payment systems and proposed combinatorial heuristics evaluated on synthetic simulations. Shafransky and Doudkin [2] investigated branch-and-bound optimization for liquidity netting. Recently, Cambe and Xing [22] introduced the 'Just Solve It' thesis, formulating the BCP as a mixed-integer linear program (MILP) solved using modern off-the-shelf solvers (Gurobi). They demonstrated that mathematical programming outperforms legacy clearing heuristics in over 91% of synthetic RTGS queue simulations. However, prior empirical validations remained confined to synthetic queuing models or small topologies (such as Xing's doctoral dissertation [23], which evaluated n = 37 banks). Whether exact solvers remain computationally viable on genuine, large-scale financial obligation networks with tens of thousands of participants and heavy-tailed dollar distributions has remained an open question.

Güntzer, Jungnickel and Leclerc [1] investigate the BCP on a large national interbank payment system and suggest some simple heuristics, tested by simulation. Shafransky and Doudkin [2] describe an optimisation algorithm for the same problem. The baseline that is considered in this paper is the well-known greedy one: sort all edges in decreasing order of their weights, and accept edge as long as the net position of the payer does not exceed his deposit. The sorting phase takes O(m log m) while scanning with a hash map of the running net positions takes O(m), so the overall complexity is O(m log m) time and O(n+m) space. This heuristic is structurally close to the fractional knapsack algorithm with the budget per node. This is a simple and solver-free heuristic with no foresight and guarantee. There are two standard enhancements: local search (adding or swapping arcs after the greedy phase) and LP-guided rounding (solving the LP relaxation and accepting arcs based on their fractional values). Both techniques are not particular to the BCP, and both will be considered as baselines in Section 9.8.

Graph partitioning algorithms such as Spectral and Multilevel like METIS [10] partition the graph into balanced partitions for parallel computation. The time complexity of a basic Spectral Algorithm is roughly O(n³) for computing the eigen decomposition, whereas that of multilevel is linear per iteration leading to O(m log n) in total time, O(n + m) being the space. They perform very well on meshes and circuit netlists, which have balanced partitions. In scale-free graphs, no such partitions exist, and balancing might cut off hubs from their spokes or even the expensive hub to hub communication channels. This category is included in the comparative analysis for completeness and has not been proposed for BCP.

Bech and Soramäki analyze gridlock resolution in payment systems [3], whereas Soramäki et al. analyze the topology of Fedwire payment flows [4]. A core and periphery are introduced for a national interbank market by Craig and von Peter [5]. Eisenberg and Noe [6] use the idea of a clear vector of payments in a network with continuous partial payments. Schuldenzucker, Seuken and Battiston prove that clearing in the case when there are credit default swaps is PPAD-complete [7]. While all these works assume continuous clearing and not BCP, it is because of them that the structure of the network becomes important at all.


### 5.2 Comparison of Advantages and Limitations


**Table 1 compares the approaches. Every existing approach either gives the best quality and pays for it in worst-case time, or runs fast and gives no guarantee, and none of them uses the hub-and-spoke shape of the network.**


**Table 1. Comparison of existing approaches and the proposed HSC.**


### 5.3 Research Gap

From the sources above, we can observe two missing elements. The first one is that none of the BCP approaches mentioned above utilizes the hub and spoke structure of payment networks to decompose the problem while ensuring the existence of a feasible clearing. The second one is that in the BCP approaches found by us, there is no information on the usage of public networks as a testbed since these studies use either synthetic graphs or proprietary datasets such as Fedwire or TARGET2 from central banks. This paper tries to cover both of these missing points, but within the constraints specified in Section 10.3. In addition, we conduct comparisons with local search and a time-matched exact solver which are absent in this problem’s literature.


## 6. Problem Statement


### 6.1 Input and Output

Input is a directed graph G = (V, A) with n banks. Each arc (u, v) has an arc-weight w(u, v) > 0, representing the payment responsibility of bank u to bank v; each vertex v has a deposit capacity deposit(v) ≥ 0. The proposed algorithm uses one more input: the budget of the hub k.

Output is a clearing X ⊆ A, representing the obligations that will be fulfilled. Clearing needs to be optimal in the sense that it maximises the cleared volume, which is defined as the sum of w(u, v) over all arcs in X, but subject to one constraint per each bank v, namely that the net position of bank v, defined as the cleared arc-weight out of v minus the cleared arc-weight into v, cannot exceed deposit(v).

Formally, as an integer programme, x(u, v) is either 0 or 1, depending on whether or not the arc is cleared. Then we seek to maximise the sum of w(u, v) · x(u, v), with the constraints that, for each bank v, the difference between the cleared out-degree and the cleared in-degree is at most deposit(v).


### 6.2 Constraints and Assumptions

The network may have mutual arcs (where u owes v and vice versa), which is often the case for trading networks.

The net outflow of each bank is only supported by its deposit, and the money received reduces that outflow.

Either an order is cleared entirely, or it is not cleared at all. Partial clearing is not possible because of the discrete nature of the problem [1], [2].

The network, the weights and the deposits are known to the central clearing entity while making the decision, just like in the case of the centralized clearing entities (Fedwire, CHIPS, or national RTGS).

The decision variant of the problem (whether or not there exists a feasible solution with the value of at least V) is known to be NP-complete [1], [8]. So, exact methods for it cannot have a polynomial time bound, unless P=NP. Of course, we don’t argue with that. The idea is that real structure of the network can help to reduce the computations.


### 6.3 Illustrative Scenario

Consider the case of a national real-time clearing network which processes around 50,000 payment orders per cycle among 800 member banks, and where the sum of the debits equals about three times the sum of the reserve credits. It is not possible to settle everything. From research on networks such as Fedwire, it has been found that a relatively small number of large, highly connected banks (money-center and clearing banks) hold a disproportionate amount of the flow, while most banks interact only with a few other banks [4]. In the generic approach, this information is ignored and the problem is solved anew with all 800 banks and tens of thousands of arcs per cycle. HSC will identify 20 to 40 true hubs, solve the core problem, and handle the rest of the spoke banks independently.


## 7. Proposed Methodology


### 7.1 Overview and Main Idea

In HSC, the bank set is divided into a small hub set H consisting of k banks with the highest degrees and the spokes set S comprising everyone else. The spokes are not mutually isolated. There are arcs between the spokes in the data; otherwise, they will lead to throwing out cleared volume or erroneous decomposition. Thus, in the spoke-only network, we decompose the network into connected components, where every component corresponds to one super-spoke. Any connection between the super-spokes must traverse a hub since there is no arc between two separate components. It follows that once the hubs' level is decided, what will happen at the super-spokes is independent of everything except the arcs inside the super-spokes and connections between them and the hubs.

The exact optimisation problem is thus restricted to hubs plus one pooled node for each super-spoke, while the arcs within the super-spokes are cleared in an easy greedy way.

The exact ILP solver and the greedy algorithm are taken as-is, i.e., they are not modified in any way. The novel contribution in this case consists of the following four elements: (a) the rule for partitioning the problem (hubs and spokes according to degrees and aggregation of connected groups of spoke vertices into super-spokes), (b) the proof that such partitioning guarantees independence of resulting components, (c) a bug in implementation of the algorithm, discovered during coding, in which the pooled deposit could take an obligation larger than the one any single member bank could bear, and (d) the adaptive rule for hub budgets of Section 7.9. The cover page and earlier versions of the paper refer to the algorithm as FPT Hub-Spoke Clearing, but it is referred to as HSC in the text, as the technique is inspired by fixed-parameter tractability [9], although this is not formally proven.


### 7.2 Step-by-Step Procedure

Compute the degree of every bank (in-degree plus out-degree). The k banks with the highest degree form H and the rest form S.

Build the undirected spoke-only graph and find its connected components with union-find. Each component becomes a virtual node whose deposit is the sum of its members’ deposits, and its arcs to and from each hub are added up into aggregates.

Solve a 0/1 ILP on the hubs plus the virtual nodes. This is the f(k) step, the only part with exponential worst-case cost.

For every cleared aggregate outgoing obligation of a super-spoke, commit the member arcs in descending order of weight, but only while each member’s real remaining budget allows it. Cleared incoming arcs are always safe for the spoke side, because they only add budget.

Clear the internal spoke-to-spoke arcs of each super-spoke greedily, using the budgets that are left.

Recompute every bank’s true net position. While some bank is above its deposit, delete the least valuable cleared arc leaving that bank, and repeat until nobody violates a deposit.


### 7.3 Pseudocode

CLASSIFY-HUBS-SPOKES(G, k):

for each bank v: degree(v) <- indeg(v) + outdeg(v)

H <- the k banks of highest degree        // ties broken arbitrarily

S <- V - H

return H, S

COLLAPSE-SUPER-SPOKES(G, H, S):

components <- CONNECTED-COMPONENTS(spoke-only graph)   // union-find

for each component C:

create virtual node ss_C; deposit(ss_C) <- sum of deposit(v), v in C

for each hub h:

agg_out(ss_C, h) <- sum of w(v, h) over v in C   // spoke -> hub

agg_in(h, ss_C)  <- sum of w(h, v) over v in C   // hub -> spoke

return components, agg_out, agg_in

HUB-SPOKE-CLEARING(G, deposits, k):

H, S <- CLASSIFY-HUBS-SPOKES(G, k)

components, agg_out, agg_in <- COLLAPSE-SUPER-SPOKES(G, H, S)

X_hub <- EXACT-ILP-SOLVE(hubs + virtual nodes)          // cost f(k)

for each component C and hub h with agg_out(ss_C, h) cleared in X_hub:

for v in C sorted by w(v, h) descending:

if w(v, h) <= remaining_budget(v):

commit (v, h); remaining_budget(v) -= w(v, h)

for each component C and hub h with agg_in(h, ss_C) cleared in X_hub:

for v in C: commit (h, v); remaining_budget(v) += w(h, v)   // always safe

for each component C:

X_C <- GREEDY-CLEAR(internal arcs of C, remaining_budget)

X <- hub-hub arcs of X_hub  U  rationed arcs  U  all X_C

X <- REPAIR(X, deposits)

return X

REPAIR(X, deposits):

while some bank u has netpos(u, X) > deposit(u):

remove from X the cleared arc leaving u with the smallest weight

return X


### 7.4 Flowchart / System Architecture

The figure below illustrates the stages in a pipeline form. At the input stage, we have an obligated graph with weighted arcs and deposits along with the budget for hubs, while the output consists of a feasible clearing. The third stage is the only costly one and works on the basis of hubs and super-spokes.


*Figure 1. Flowchart of Hub-Spoke Clearing (HSC).*


### 7.5 Worked Example (10 Banks)

To be more specific, consider a 10 bank example, where the skeleton has a scale-free structure, with k = 3. Here, the deposits of each bank are {0: 14, 1: 9, 2: 8, 3: 22, 4: 13, 5: 8, 6: 16, 7: 14, 8: 9, 9: 17}. Here there are 23 arcs, with the notation u→v (weight): 0→1 (6), 0→2 (10), 0→3 (1), 0→8 (10), 1→0 (7), 1→4 (7), 2→0 (3), 2→4 (8), 2→6 (5), 2→7 (5), 3→5 (1), 3→8 (5), 3→9 (3), 4→3 (2), 4→7 (4), 4→8 (6), 5→0 (6), 5→2 (10), 6→0 (5), 6→4 (6), 7→6 (6), 7→9 (1), 9→6 (10).

The highest degree is of Bank 0 (8). The degree of Banks 2 and 4 is 6, and all other banks have a degree of 5 or below. This makes H = {0, 2, 4}, and S = {1, 3, 5, 6, 7, 8, 9}.

The arcs that have spokes only include 3→5, 3→8, 3→9, 7→6, 7→9 and 9→6. These when read as undirected arcs make {3, 5, 6, 7, 8, 9} a single super-spoke. As Bank 1 does not have any spoke to spoke arcs since it connects to hub banks 0 and 4 only so seven spoke banks end up as two super-spokes.

The hub-level rationing rule eliminates the aggregate burden of the large super-spoke in paying 11 units to hub 0 and 6 units to hub 4, but not 10 units to hub 2 (which can be satisfied only by bank 5). The rationing process now considers each member separately. While bank 5 can pay 6 units to hub 0, it cannot pay 10 units to hub 2, hence this obligation gets eliminated at the member level although it was feasible in the aggregate level. One fixing gets triggered in this run. HSC finds the exact optimum solution whereas the greedy algorithm misses 17 units (Table 2).


**Table 2. Worked 10-bank example.**

This is one illustrative instance and not evidence that HSC is better in general. The statistical comparisons come later, in Section 9.


### 7.6 How HSC Differs from the Surveyed Algorithms

Compared to the exact ILP formulation (Section 5.1), the exponential factor is only in the k-hub subproblem, as opposed to the entire n-bank graph. As seen in Section 9.2, there is a noticeable speed-up on our test machine due to this property, with the speed-up increasing with n but remaining small.

When checking with unstructured greedy, the same greedy algorithm is applied, but only to each spoke subgraph, after the hub subgraph applies the exact and non-myopic step of determining the maximum value obligations. The previous limitation of greedy – lack of look-ahead – now affects only the less valuable part of the problem.

Against general graph partitioning, the division does not attempt to keep the size of the subgraphs equal; instead, it attempts to split apart the nodes of high degree. The independence of the subgraphs then derives from the connected-components definition of the subgraphs, and not from balancing.


### 7.7 Correctness and Feasibility

Decomposition independence

The super-spokes are nothing but the connected components of the spoke-only graph; hence there can be no arc between two components. In any path connecting two such components, the path must go through the hub. Once the decision at the hub is taken, the clearing within the component would be dependent only on the arcs within the component and the position of the component relative to the hub. This is because the feasibility of the bank depends only on its own net position and deposit, and not the joint position of other banks.

A pooled-deposit problem and its two-stage fix

The pooled deposit of a super-spoke, which is simply the sum of the deposits of its members, is the maximum possible collective capacity of the super-spoke. The problem is that the hub ILP may take on aggregate liability that exceeds what any one member can possibly assume individually. In our initial approach to implementing HSC, we ended up with clearings whose cleared volume exceeded the optimum, which cannot be done in reality. We observed this in our stress test against the optimal clearing volume. There are two ways to solve this problem: (1) rationing with respect to the actual deposits of the members (step 4), and (2) the fixing step (step 6).

Why the returned clearing is feasible

There are three components to the argument. First there is a loop-invariant argument regarding the spoke banks, second there is a comment on the hubs, and third is the termination of the repair phase.

Lemma 1 (feasibility of spoke banks maintained through steps 4 and 5). Let net(v) be the current net position of a bank. The invariant is that, after each super-spoke is processed, all banks in it satisfy net(v) ≤ deposit(v). Initialization: initially net(v) = 0, hence inside the deposit. Maintenance: an outgoing arc of spoke bank is committed only after the condition net(v) + w ≤ deposit(v) is satisfied in both rationing and local greedy phases. An incoming arc to spoke bank v reduces net(v). The super-spokes have disjoint arcs, so processing of one component will not affect the spoke banks of another component. Termination: the loop terminates after all p super-spokes, after which all spoke banks satisfy their deposit.

Remark (hubs may be in violation prior to repair). The hub ILP ensures that the constraints of the hubs are satisfied only if all the arcs that were cleared were committed fully. In the rationing phase, less than the entire obligation to the hubs is committed, causing a situation whereby the hub lacks incoming flow that was supposed to come through the ILP. The hub can therefore be in violation of its deposit, and this happens because of the arcs that were rationed.

Lemma 2 (repair will halt with a feasible clearing). Assume that for bank u, net(u) > deposit(u) ≥ 0 holds true. This implies that the cleared weight of arcs leaving bank u is larger than the cleared weight of arcs entering u, and thus u has at least one cleared arc leaving u, making it always possible to perform a deletion. The deletion process always deletes an arc from set X, and hence the loop is executed at most |X| times. If we delete arc (u, v), then net(u) becomes smaller by w, whereas net(v) becomes larger by w; this might cause net(v) to exceed its deposit. This is why the loop executes until nobody violates, not only once per bank. At the end of it, no bank violates its deposit by definition of the loop termination criterion, and all net positions would become zero, which is feasible.

Theorem (feasibility). All clearings computed by HSC have net(v) ≤ deposit(v) for all banks v. This can be directly deduced from Lemma 2, regardless of how the hub ILP and the rationing phase performed. This lemma is the reason why in most cases the repair phase doesn’t have much work to do on the spokes.

In all our benchmarks and real data runs, all the clearings were checked by recomputing net positions, and none was found to be infeasible. As a second test of consistency, we run 190 stress tests on graphs with scale-free distribution (n = 10, 20, 40, 80 and 120, and without hubs, n = 50 and 100, and 20-40 seeds each). None of the clearings generated there had value higher than the exact optimum (0 out of 190). This test cannot prove feasibility, because a feasible clearing does not necessarily exceed the optimum, and the above proof does that.


### 7.8 Approximation Analysis

Section 7.7 observes that HSC makes no global optimality guarantees. This section discusses the provable results - a ½-approximation guarantee for the greedy spoke step under gross-outflow model, a special case, and reasons why this guarantee fails to extend to the netting model.

Under gross-outflow model, for a spoke component C, let b(v) ≥ 0 denote the remaining budget of the member v after rationing. The clearing of an arc (u, v) consumes w(u, v) units of budget from u and incoming arcs provide no relief. Any clearing that is feasible in this model is also feasible in the netting model, making the former a conservative version of the latter.

Theorem 1 (greedy-spoke ½-approximation). Under the gross-outflow model, for any spoke component C, the clearing obtained by the greedy approach (edges are admitted in descending order of their weights, as long as the source budget allows) is at least half as large as the best clearing of C: GRD(C) ≥ ½·OPT(C).

Proof, in natural language. Budget constraints are defined on disjoint subsets of out-arcs (one per source bank), so OPT(C) is equal to the sum of OPT(u) over all source banks u, where OPT(u) is the best subset of out-arcs of u whose weights do not exceed b(u). Greedy admits each arc based on the current budget sum at its own source bank, and hence GRD(C) is equal to the sum of GRD(u). It is therefore sufficient to show that GRD(u) ≥ ½·OPT(u) for one bank. Out-arcs having weight greater than b(u) cannot be part of any feasible clearing and thus can be discarded. If all of the remaining out-arcs were admitted by greedy, then GRD(u) = OPT(u). Otherwise, let e be the first out-arc rejected by greedy and G be the sum of the weights of all admitted edges before e. The rejection implies that G + w(e) > b(u) and hence GRD(u) ≥ G ≥ max(w(e), b(u) − w(e)) ≥ b(u)/2 ≥ OPT(u)/2. Summing over all banks u gives the claim

This bound cannot be improved for the greedy algorithm. Consider an example with budget 2 at a single node with outgoing arcs of weights 1+ε, 1, and 1; here GRD = 1+ε and OPT = 2 and the ratio approaches ½ arbitrarily. As k tends to n, the spoke set is empty and HSC coincides with the exact ILP, so HSC(G) = OPT(G) asymptotically. For netting, the situation is drastically worse: a constant-ratio guarantee does not even hold for pure greedy. Construct a chain x₀ → x₁ → … → xₙ, where the arc from xᵢ to xᵢ₊₁ has weight 2ⁱ, while the bank x₀ has budget 1 and xᵢ has budget 2ⁱ⁻¹, i ≥ 1. Clearing the chain is feasible since the outflow of every node is covered by its inflow and its budget, so OPT = 2ⁿ − 1. Greedy starts with the heaviest arc and finds out that the source has no inflow yet and insufficient budget. This happens on every arc in the chain, so greedy accepts only the arc of weight 1, and the ratio equals 1/(2ⁿ − 1). No ratio guarantee for the full algorithm is proven. The pooled-deposit relaxation and the repair pass both change which arcs survive, so the quality of the full algorithm is judged empirically.

Theorem 1 implies more than it seems to say. The spoke phase for each source bank constitutes a subset-sum problem and there exists a fully polynomial time approximation scheme for subset sum [18] and therefore a (1 − ε) guarantee for each bank is obtainable with minimal expense. The ½ guarantee refers to the particular greedy choice made, but does not provide any information regarding the performance of the overall algorithm. Using a dynamic programming technique for the spoke phase would be an obvious improvement.


**Table 3. Summary of guarantees.**


### 7.9 Adaptive Hub Budget (select_k_adaptive)

The algorithm for Sections 7.1 to 7.7 requires the user to provide k. However, in the real scenario the natural hub core is determined by the degree distribution where hubs are the banks with degree much higher than the average degree. This is expressed using the degree-ratio boundary. Considering a value of τ = 3.0, the hub core contains all the banks having degree larger or equal to the maximum degree/τ. The adaptive budget k is defined as the cardinality of the hub core within the interval [k_min, k_max_frac · n].

The sorted degrees have been smoothened using a window of size 3, and the boundary is the first position such that maximum degree/degree at that position is greater or equal to τ. Otherwise, if such a position does not exist, in case of a flat graph the largest proportional gap between consecutive degrees is taken into consideration. If the value of that gap is lower than 0.15, then k_min is returned.

select_k_adaptive(G, tau, k_min, k_max_frac):

1. deg(v) <- indeg(v) + outdeg(v) for all v

2. sort degrees descending: d_0 >= d_1 >= ... >= d_(n-1)

3. smooth the sorted sequence with a sliding window (window = 3)


### 4. i* <- first index with d_0 / d_i >= tau        // degree-ratio boundary


### 5. if no such i* exists (flat graph):

i* <- argmax_i (d_i - d_(i+1)) / d_i        // largest proportional gap

if that gap < 0.15: k <- k_min              // flat-graph floor


### 6. return k = clip(i*, k_min, floor(k_max_frac * n))

This rule uses one O(n log n) sort that has already been paid by the hub ranking algorithm, thus, there is no change in complexity at all. We set τ = 3.0 due to the heavy tail nature of the degree distribution of payment networks, whose exponent is close to 2 [4]. In other words, there will be only a few banks with the degree close to the maximum. There is one drawback of the rule. It depends on the maximum degree; therefore, k remains close to 16 for n from 250 to 1000 (Section 9.5).


### 7.10 Time and Space Complexity

Let n be the number of banks, m the number of arcs, k the number of hubs, and p the number of super-spokes. Going through the steps one by one:

Classification costs O(n log n). Degrees take O(n + m), and picking the top k by sorting takes O(n log n) (a linear-time selection would also work).

Collapsing with union-find costs O(n + m) up to the inverse-Ackermann factor [16].

Rationing costs O(n log n) in total, because each spoke bank belongs to exactly one component.

Local greedy costs O(m log n) in total, since the internal arcs of all components add up to at most m.

Repair removes at most one arc per step and costs O(m log n) with per-bank sorted lists.

The exact hub step costs f(k, p). The hub ILP has the hub-to-hub arcs (at most k² of them) plus at most 2kp aggregated hub-to-super-spoke variables, so it depends on the number of super-spokes as well as on k. We write f(k) for short. In the worst case f is exponential in the size of that ILP, and Table 7 shows how big the ILP really is in practice.

The overall complexity will be O(n log n) + O(m log n) + f(k), which is O(n log n) + f(k) in case of a sparse network where m = O(n). Memory complexity is O(n + m + k²) plus aggregated arcs, which is the same for both baselines, except that we have the additional k² component due to the hub subproblem. For the adaptive version, we need to add one sorting, and thus, the overall complexity will be the same, but with k replaced with the auto-selected one.


**Table 4. Complexity and guarantees.**


### 7.11 Implementation

The three algorithms (exact, unstructured greedy and HSC) were all coded in Python 3 using the same instance generator and NetworkX representation [14], so each algorithm has been tested against the identical BCP instance. The exact algorithm is the 0/1 ILP shown above, solved by CBC via PuLP [11], [12]. The console output of the 10-bank example in Section 7.5 comes from a session on the author’s personal Windows machine (Figure 2). This session recreates the four original experiment sweeps (six trials per size for the two main sweeps, five trials per data point for the other two), which were used for development and checking. The results in Section 9 use the larger 30-trial re-benchmark that replaces these sweeps, while keeping only the structural statistics of the 6-trial sweep (Table 7).


*Figure 2. Terminal session reproducing all four original experiment sweeps end to end (6 trials per size for the main and no-hub sweeps, 5 trials per point for the hub-budget and density sweeps).*

The part of that output that belongs to the worked example is:

DEPOSITS {0: 14, 1: 9, 2: 8, 3: 22, 4: 13, 5: 8, 6: 16, 7: 14, 8: 9, 9: 17}

H = {0, 2, 4}   S = {1, 3, 5, 6, 7, 8, 9}

super-spokes = [{1}, {3, 5, 6, 7, 8, 9}]

EXACT  volume=114  time=0.0050s  (ground truth)

GREEDY volume=97   time<0.0005s  (85.1% of optimum)

FPT    volume=114  time=0.0049s  super_spokes=2  repairs=1  (100.0% of optimum)


## 8. Experimental Setup


### 8.1 Dataset / Input Details

In scale-free instances, a Barabasi-Albert graph [15] with mba = 3 is used as an undirected skeleton. All edges are then oriented randomly, and with a probability of 0.3, a reverse arc is included, thus establishing bilateral obligations. The weights are uniformly distributed from 1 to 10, and deposits are from 8 to 25.

In no-hub instances, these are Erdos-Renyi graphs with weights and deposits as in scale-free instances but with an equal expected number of neighbors for all banks, thereby eliminating the hubs deliberately and providing the worst-case scenario for HSC.

Tight-deposit instances are a stress test that uses scale-free instances with deposits from 3 to 12 and a bilateral arc probability of 0.4. Here, n is from 500 to 4000 (see Section 9.7).

Real-life transaction graphs are Bitcoin OTC and Bitcoin Alpha graphs from the Stanford SNAP database [17]. Each positive-weighted directed rating (u → v, w) is regarded as an obligation of w units from u to v, while negative ratings (dislikes) are ignored. Deposits are defined as deposit(v) = max(1, round(0.6 * total_in(v))). 0.6 is a liquidity ratio based on the liquidity rule introduced in Basel III agreement [21] - in layman terms it means that a participant can only pay out up to 60% of inflow. Those are trust networks among users, serving as obligation networks proxies, deposits being artificial. They are used to evaluate the algorithm on real-world, heavy-tailed and transaction-like topology, but not on interbank payments data. Table 5 shows their characteristics and Figure 3 shows console output of data loading process.


**Table 5. Properties of the real datasets.**


*Figure 3. Console output of load_real_data.py: dataset statistics, power-law exponents and the four temporal slices of Bitcoin OTC.*


### 8.2 Experimental Environment

All experiments used Python 3.12.10 on Windows 11 (16 GB RAM), NetworkX 3.6.1 to represent the graph, and PuLP 3.3.2 with the default solver CBC 2.10.3 for all ILP formulations. In all three algorithms — exact ILP formulation, unstructured greedy heuristic, and the FPT Hub-Spoke Clearing algorithm — identical instances run in the same codebase. Single-machine absolute times are provided as ratios unless indicated otherwise. All tables in Section 9 employ 30 trials per data point except where noted explicitly. For the real-world data experiments in Section 9.6, the Bitcoin OTC and Bitcoin Alpha graphs are loaded from the SNAP Stanford network data files [17]. For the tight-deposit stress testing in Section 9.7, there is a hard wall clock time limit imposed using the PuLP interface, and all solutions, including CBC timeouts, have been independently verified as feasible.


### 8.3 Parameters

Allocation: hub budget k = 6% of n (rounded) for the fixed version on synthetic graphs, k = 80 for the real graphs, and select_k_adaptive (τ = 3.0, smoothing window 3, flat-graph threshold 0.15) for the adaptive version.

Number of trials: 30 independent random runs per data point in Sections 9.2–9.5, 5 runs per cell in the stress test (Section 9.7), and 256 weekly runs in Section 9.6.

Real-world data: liquidity ratio = 0.6, and the subgraph test uses 300 largest-degree vertices in Bitcoin Alpha graph.

The time limits in the stress test: exact T = 1, 2, and 5 s. The time limit for the hub ILP problem of HSC is separated from other problems, hence HSC running time includes all time used by the solver, while CBC is limited to T.


### 8.4 Evaluation Metrics and Statistical Protocol

The cleared volume (weight of arcs in returned feasible clearing) and its percentage of the optimum, which is defined as the exact solver of the same instance. In our stress tests, we use percentage of CBC volume instead.

The difference between HSC and greedy methods in percentage points (pp) along with the p-value and variability.

The wall-clock time (high-resolution timer around the entire run of each algorithm), speedup compared to the exact solver, number of hub-ILP variables, number of super-spokes, and number of repairs.

Feasibility via recalculation of net position for each bank directly.

Each algorithm gets the same random problems (the same seeds per problem), hence all tests are paired according to problem. The p-values mentioned refer to the 30 differences per problem between the FPT Hub-Spoke Clearing and the unstructured greedy heuristic for the difference in cleared volumes. The “±” values for all the tables are 95% confidence interval half-widths, calculated as SEM × t*(df=29) = SEM × 2.045, where SEM is the standard error of the mean for the 30 experiments. Values that appear as "<0.0001" represent p-values of exactly 0.0000 in the output file, but we consider them as p = 0.0001 for correction. As there are eight tests reported in Table 6 simultaneously, Holm’s step-down correction has been done on those p-values. The maximum Holm-corrected p-value for the six significant tests is 0.011 (n = 18), hence the conclusion does not change even after correction for multiple comparisons. The two insignificant results (n = 30, p = 0.848; n = 50, p = 0.499) have been indicated as such, and there is no claim of superiority in those sizes. The protocol for the revision experiments (Section 9.8) was specified in advance as follows: paired t-test on differences per instance, with a Wilcoxon signed-rank test as a check; 95% confidence intervals for the mean of paired differences; Holm correction for each set of comparisons; and “±” always denoting the standard deviation of the samples over the 30 instances. The fact that trials have a common seed within each row makes comparisons between rows dependent.


### 8.5 Existing / Baseline Algorithms Selected for Comparison

The comparison in the original paper is done against two baseline algorithms: exact 0/1 ILP and unstructured greedy. The heuristics mentioned in [1] and [2] are not implemented again in the new study. Four additional components are added to the experimental results: greedy + local search, LP rounding, exact solution that was terminated at the same time as HSC, and HSC with different selection criteria for hubs.


## 9. Results and Discussion


### 9.1 Feasibility

Each clearing solution generated by HSC during the benchmarking phase as well as from the real data was found to be feasible through re-computation. The repair stage ran several times (e.g., 18 times for the entire Bitcoin OTC graph and 6 times for Bitcoin Alpha), hence proving that it is a functional element of the algorithm rather than a theoretical measure alone. As mentioned in Section 7.7, the 190-instance test against the optimal is simply a consistency test.


### 9.2 Scale-Free Networks

Greedy and HSC (k = 6% of n) were compared on scale-free instances of eight sizes, with 30 trials per size.


**Table 6. Scale-free networks, quality as % of the true optimum (30 trials per size).**


*Figure 4. Solution quality (a) and running-time ratio (b) of HSC on scale-free networks (data of Table 6; error bars as in the table).*

HSC performs significantly better than greedy at n = 10, 18, 100 and all n ≥ 250 (+2.29 to +3.60 pp, p < 0.0001 for n ≥ 250), getting 90–92% of the optimal value compared to only 88% for greedy. For n = 30 and 50, there is no significant difference (−0.13 pp with p = 0.85, and −1.24 pp with p = 0.25). An initial run of six trials indicated an obvious disadvantage for n = 50, but 30 trials failed to show any significant difference.

The CBC solved all problems to optimality in less than 0.3 seconds per problem in the development run, so the algorithm was feasible for all problem sizes. The relative speedup of HSC increases from 1.07× to 3.39× at n = 500 and 2.78× at n = 1000. The advantage of a parametrized algorithm is apparent, but not inevitable for these random problems.

The poor performance at n = 30-50 could perhaps be explained by the low budget of hubs (just 2 or 3 banks) in the model, causing a course partition into hubs and spokes, and thus allowing greedy to exploit spoke-to-spoke value, which the rationing strategy cannot exploit. At n = 10 and 18, the hub ILP is responsible for a large portion of all arcs (see Table 7), explaining the high gain at these sizes. The data do not allow us to conclude the cause of this, but at n = 100 the hub ILP takes up a small portion of all arcs, while HSC wins, so this explanation is just a conjecture.


**Table 7 demonstrates the motivation of our heuristic approach in the first place. The exact step starts with a hub ILP having from 10 to 414 variables compared to an arc set, saving 2.3 times at n = 10, reaching 16.6 times at n = 50 and 9.4 times at n = 1000.**


**Table 7. Hub-subproblem size (6-trial development run, absolute CBC times).**

These are 6-trial values, so the time ratios differ somewhat from the 30-trial speedups in Table 6 (for example 2.6× against 3.39× at n = 500).


### 9.3 Networks without Hubs (Worst Case)

To test the limitation we stated up front, the same algorithms were run on Erdős–Rényi graphs with n = 200 and no degree skew, changing only k/n.


**Table 8. Erdős–Rényi networks, n = 200 (30 trials per row).**


*Figure 5. Quality on no-hub networks as the hub budget k/n grows (data of Table 8).*

This is probably the clearest negative effect of the experiment. For k = 3% of n, HSC performs considerably worse than the greedy algorithm and for 10% it is indistinguishable from it. Labelling the nodes with the highest degree as hubs when there are no actual hubs gives no additional information, which was expected. The quality of the solution is getting better only when k approaches n, but then the hub ILP contains more than 750 variables and the running time is comparable to that of the exact solver (0.198 s versus 0.244 s per 6 trials). Thus, HSC is becoming the exact solver when k increases and in the unstructured network it costs almost the same as exact solving for almost the same quality.


*Figure 6. Console output of Experiments 1 and 2 (main scale comparison and no-hub comparison), 30 trials per point.*


### 9.4 Hub Budget and Network Density

The hub budget only means something when hubs exist, so we swept it on a scale-free network (n = 250, 30 trials). Greedy does not depend on k, and its quality at n = 250 is 88.0%.


**Table 9. Hub-budget sweep on scale-free networks, n = 250 (greedy = 88.0%).**


*Figure 7. HSC quality (line) and hub-ILP size (bars) as the hub budget grows, n = 250 (data of Table 9).*

In the presence of hubs, quality increases gradually with k, from 86.24% for k = 5 to 95.28% for k = 40. It is not profitable to have a very small core, as HSC does not outperform greedy for k = 5 and 10 and it overtakes greedy for k ≥ 20. The cost of having a large core is obvious in the last two columns: the hub ILP model uses 17 times more variables and it runs much slower. As we see, starting with k = 20, the time of HSC (0.13 s) becomes longer than the exact-solver time at the same n (0.12 s) in Table 7. This point will be discussed in Section 9.8.

Then, we varied the density of the graph. In this experiment, n = 100, k equals 8% of n, and m_ba (the number of edges added by each new node in Barabási–Albert) increases.


**Table 10. Effect of network density, n = 100, k = 8% of n (30 trials per row).**


*Figure 8. Quality (a) and running time (b) as the network becomes denser, n = 100 (data of Table 10).*

For both methods, the quality decreases as the graph becomes more dense (the greedy algorithm from 94.35% to 81.61%, HSC from 98.35% to 84.23%). HSC remains superior, however, with the difference reducing from 4.00 to 2.62 pp. The earlier test for six trials showed an increasing difference with higher density; however, this is not the case for thirty trials, so we refrain from stating this. Time saving increases, however, with density. HSC competes even with the exact solver at the near-tree graph (0.0935 s against 0.0967 s), and is 2.5 times faster than the exact solver at m_ba = 8 since the latter is extremely expensive to compute while the former increases slightly.


### 9.5 Adaptive Hub Budget

The adaptive rule of Section 7.9 was compared with the fixed 6% budget on scale-free instances, 30 trials per size.


**Table 11. Adaptive versus fixed hub budget (30 trials per size).**


*Figure 9. Greedy, HSC with fixed k and HSC with adaptive k as n grows (data of Table 11).*

For n = 50 and 100 the adaptive rule picks a larger core than 6% of n and is significantly better than both fixed k and greedy (93.66% at n = 100).

At n = 250 it picks k ≈ 15.6, very close to the fixed value of 15, and the two cannot be told apart (p = 0.82). The rule finds a sensible budget on its own.

For n ≥ 500 the rule fails. The selected k stays near 16 while the fixed budget grows with n, so adaptive is 2.55 and 3.38 pp worse, and at n = 1000 it is no better than greedy (87.84% against 87.63%). The degree-ratio boundary does not scale with n. A larger k_min or a different τ would be needed, which we leave to future work. The main HSC result does not depend on the rule, since the fixed budget does not fail.

The HSC-Fixed value at n = 250 is 90.29% in Table 6 and 89.70% in Table 11, for the same n and k = 15. They come from separate runs of 30 random instances, so the difference is run-to-run variation and the digits should not be expected to agree across tables.


*Figure 10. Console output of Experiments 3, 4 and 5 (hub-budget sweep, density sweep, adaptive k), 30 trials per point.*


### 9.6 Real Transaction Networks

Full graphs

Both exponents of power laws are very close to 2, just like that of the Fedwire network [4], conforming to the scale-free property. While our initial intuition assumed the full transaction graphs would be intractable for exact optimization, executing real_exact_check.py using HiGHS solved both networks to true mathematical optimality in 1.55 seconds (Bitcoin Alpha, optimum = 42,173) and 2.46 seconds (Bitcoin OTC, optimum = 57,409). Table 12 reports the full comparative evaluation including the true exact baseline and greedy with local search. HSC achieves 92.7% to 93.0% of the true optimum (84.6% to 86.8% of total obligations), while Greedy + Local Search reaches 98.3% to 98.4% of optimum in approximately 0.1 seconds.


**Table 12. Full-graph results on real networks with verified exact optimum and Greedy + Local Search.**

As Table 12 demonstrates, HSC-Fixed clears 84.56% (OTC) and 86.75% (Alpha) of total obligations, reaching 92.72% and 92.98% of the true mathematical optimum in 4.69 s and 2.36 s. In comparison, Greedy + Local Search clears 89.74% (OTC) and 91.71% (Alpha), reaching 98.40% and 98.30% of optimum in just 0.13 s and 0.09 s. The exact solver HiGHS determines the true optimal clearing in 2.46 s and 1.55 s. This establishes that modern exact solvers solve empirical transaction networks to provable optimality in seconds, while simple local search comfortably outperforms hub-spoke decomposition in both solution quality and computational speed.

Subgraph with an exact reference

To get ground truth on real data, we took the 300 highest-degree nodes of Bitcoin Alpha (6,663 edges, total weight 14,957, from the largest weakly connected component of 3,670 nodes) and ran all four algorithms on it, including the exact ILP.


**Table 13. Bitcoin Alpha, 300 highest-degree nodes, with exact reference.**

HSC-Fixed reaches 98.01% of the exact optimum in 0.1465 s, which is 6.8 times faster than the exact solver (0.9986 s), for a loss of 1.99 pp. Its margin over greedy (97.42%) is only 0.59 pp, and greedy is already very close to optimal here. So the result shows that the decomposition loses little compared with exact solving, not that it beats greedy by much.


*Figure 11. Console output of Experiment 6, Parts A and B (full-graph comparison and subgraph exact-ILP reference).*

Temporal slices

Bitcoin OTC was divided into four equal-width time windows, to see whether the topology and the results change over the life of the network.


**Table 14. Bitcoin OTC, four equal-width temporal slices.**

All four slices have an exponent near 2 (2.02 to 2.13). HSC-Fixed beats greedy in every slice (+0.33 to +1.27 pp). HSC-Auto wins in Q1 and Q3 and loses slightly in Q2 and Q4. In the sparse Q4 slice the rule falls back to the largest-gap criterion and selects only k = 2.


*Figure 12. Console output of Experiment 6, Part C (four temporal slices of Bitcoin OTC).*

Weekly snapshots

Bitcoin OTC was subsequently divided into 256 non-empty weekly instances from 2010 to 2016. Every week constitutes an individual BCP case where all three algorithms were applied, and for HSC-Auto, the value of k is determined anew each week. The windows are not independent of one another because of temporal dependence; however, the participants are the same throughout the process and therefore, independence does not hold. All feasibility checks have been passed.


**Table 15. Weekly snapshots, 256 instances of Bitcoin OTC.**

Over the 256 weeks, the HSC-Fixed outperforms greedy by an average of 1.69 pp and HSC-Auto by 1.22 pp, beating greedy in about 56–57 percent of weeks. The gain is genuine but small.

The automatic budget lies between 2 and 31 (with a mean of 6.26 and sd of 5.44), adjusting to the evolving size and density of the network without any adjustment from a human.

The power-law exponent estimation for a week has a mean of 4.34 (sd of 2.29, range 2.42 to 20.73). The large numbers result from sparse weekly networks where a power-law model does not apply. As such, only the full graph and slices' exponents (1.94 and 2.13) are reliable.

The weekly average cleared share (48%) is way lower than the full-graph number (84%). The most likely explanation is that the network's edges are too few in a week to enable deposits from the flow to accumulate and obligations to be settled.


*Figure 13. Console output of Experiment 6, Parts C and D, including the weekly summary over 256 snapshots*


*Figure 14. Contents of summary_real_data_weekly.csv, the source of Table 15.*

Consolidated real-data summary


*Figure 15 reproduces the consolidated summary printed at the end of the benchmark run, and Tables 12 to 14 are taken from it. Across all real-data tests HSC-Fixed is at or above greedy, HSC-Auto is mixed, and every returned clearing was verified as feasible by direct recomputation.*


*Figure 15. Consolidated console summary of Experiment 6 (real-data results) and the final feasibility check.*


### 9.7 Tight-Deposit, Time-Limited Stress Test

For larger instances with a fixed exact solver, we created scale-free graphs with dense deposits (3 to 12) and bilateral arcs of 0.4, where n varied from 500 to 4000 and there were 5 experiments per cell, with CBC being restricted by T = 1, 2, and 5 seconds. HSC is a deterministic algorithm, which is why its runtime remained constant for all the three time restrictions. The feasibility of the solutions obtained by CBC at the end of each restriction was verified. Since the ILP for the HSC hub was run separately within a time restriction, the speedup was the ratio of the full runtime of HSC to CBC restricted by T.


**Table 16. Stress test at T = 5 s with CBC (5 trials per row).**

HSC clears roughly 147% - 153% of greedy’s volume at all sizes and time limits. Greedy achieves around 30%-31% of the CBC volume (from the two ratios) and HSC roughly 44%-48%, so in tight deposits, where netting is significant, HSC manages to recover some of the deficit left by greedy.

HSC failed to outperform CBC in all the tests. CBC still finds an incumbent in the feasible range, which is twice the volume of HSC at the limit, so this test is not proof that CBC does not work at large scale. At T = 5 sec CBC solves instances for n = 500 and 1000 optimally and time outs from n = 2000.

HSC time grows from 0.25 s to 2.08 s with n. At n = 4000 with T = 1 s it is slower than CBC (0.9× speedup). Greedy stays far faster than both.

Five trials per cell is thin, so these numbers are only indicative.


### 9.8 Revision Experiments: Hub Selection, Stronger Baselines and Exact Solving at Scale

The tables shown above make the comparisons of HSC with pure greedy approach and exact solution approach. This leads to four open-ended questions: whether the improvement obtained by HSC is due to selecting hub nodes using a topology-based approach or because of solving a larger portion of the problem using exact algorithm, whether HSC fares well when compared to stronger baseline approaches like the pure greedy approach, what does exact solution approach do when provided with the same amount of time as HSC, and whether exact solution approach is practical for graphs having real data size.


#### 9.8.1 Setup and a reproduction check

These experiments employ an independent implementation of greedy, HSC, and the exact ILP using the HiGHS solver [13] via SciPy [20], rather than CBC. The instance generator is the same as those presented in Section 8.1, and the exact ILP is solved until achieving a relative gap of 10⁻⁹. All algorithms are tested on the same set of instances, where there are 30 instances per row. The hubs were selected by degree unless otherwise noted, k = 6% of n (≥ 2), and all clearings generated were verified to be feasible.

Comparison with the original results on the scale-free sweep is provided in Table 17. At a glance on single test cases, the number of arcs and number of hub-ILP variables are of similar magnitude as in the original runs (for instance, 185 arcs and 11 hub-ILP variables for n=50 against 182.8 and 11.0 in Table 7), and for n ≥ 250 HSC is better than greedy. The magnitudes, however, differ. The new greedy version obtains a result close to 89.5% against 88% in the original runs, and HSC outperforms greedy by +1.1 pp for n ≥ 500, while +3.6 pp was reported originally for n = 100, and the revised version gets a tiny deficit. The reason may be some implementation details that are not visible from the original code (tie breaking rules, rounding rule of k, arc direction generation) or simple sampling variability. We thus base all conclusions of this chapter on comparisons performed on the same instances, and we do not compare any revision numbers with Tables 6 to 16. Running the provided scripts with respect to the original benchmark code would resolve the discrepancy.


**Table 17. Reproduction check: original results (Table 6) against the re-implementation (30 instances per row). Revision differences are paired, with 95% confidence intervals.**


#### 9.8.2 Effect of the hub selection rule

HSC was run at n = 250 with four rules for choosing the k hubs: by degree (as proposed), by weighted degree (total obligation weight), at random, and by lowest degree. We used both scale-free graphs and no-hub graphs with the same expected number of arcs, with k = 15 (6%) and k = 40 (16%).


**Table 18. Hub-selection ablation, n = 250, % of the exact optimum, mean ± SD over 30 instances. The last column is degree minus random hubs, with the 95% CI and the Holm-adjusted p over the four rows.**


*Figure 16. Hub-selection ablation at n = 250 (data of Table 18). Light bars: k = 15; dark bars: k = 40.*

This property is especially crucial for the scale-free graphs. With k = 40, hubs selected based on degree perform better than random hubs by 4.66 pp (Holm-corrected p < 0.0001), random hubs perform equally to the greedy ones, and hubs selected based on the lowest degree perform worse than greedy ones by -1.01 pp (p < 0.001 uncorrected). The behavior of degree and weighted degree is similar. Thus, the relative placement of the core at the constant size of the exact core accounts for most of the advantage, proving the topology awareness of HSC. On the graphs with no hubs, hubs selected based on the degree perform equally to random hubs at k = 15, and at k = 40 they outperform random hubs by 1.5 pp, and greedy by 1.4 pp, while outperforming greedy hubs by 4.1 pp on the scale-free graphs. It is a limited ablation (only one size and two budgets) but it goes in the same direction as the no hub experiment of Section 9.3.


#### 9.8.3 Stronger baselines and a time-matched exact solver

Four baselines have been considered at n = 250 and n = 1000 on scale-free networks. The first baseline is greedy + LS, in which rejected edges are re-added and a cleared edge is replaced with a heavier edge, provided that both banks remain feasible. The second one is LP-based rounding, in which the LP-relaxation is solved, and edges are accepted greedily based on their LP-values. The third one is the optimal solution algorithm after HSC execution with k = 16%.


**Table 19. Baseline comparison on scale-free instances: % of the exact optimum (mean ± SD over 30 instances) and mean running time. All values come from the same instances.**

HSC with k = 16% beats greedy by 3.34 pp at n = 250 (95% CI 2.66 to 4.02) and 3.60 pp at n = 1000 (95% CI 3.36 to 3.84), and it beats LP-rounding by about 2.6 and 2.7 pp, respectively, with Holm-corrected p < 10⁻⁷ for all comparisons. These improvements are genuine, but local search heuristics work even better. The greedy followed by local search heuristic gets close to 99% of the optimum, which is 6.1 pp better than HSC, in about one-third of the time that HSC needs. The exact solver with a time limit equal to the HSC running time finds between 99.2% and 99.7% of the optimum. At this size, HSC is thus beat twice over: by a heuristic that is easier to code, and by an exact solver with the same amount of running time as HSC.

There are two limitations. First, we use a very simple local search, written specifically for this research, and second, HiGHS is significantly faster than CBC (CBC runtimes from Table 7, which are six-trial development values, are approximately 1.7 to 2.8 times higher). Neither caveat helps HSC against the local search, which uses no solver at all.


#### 9.8.4 Exact solver on a graph of real-data size

In section 9.6, the exact solver was left out from the complete Bitcoin graphs. In order to check if this is really necessary, we made up a proxy similar in its dimensions: a Barabási–Albert graph with n = 5,881 banks, with asymmetric integer weights having average of 2, with bilateral arcs having probability 0.3, and deposits calculated according to the real data formula (0.6 × total in-weight). The proxy graph has around 23,000 arcs, which is less than in the case of Bitcoin OTC (32,029)..


**Table 20. Synthetic proxy of real-graph size (n = 5,881; three instances). Quality is % of the exact optimum; HiGHS proved optimality in every case.**

ILP is proven optimal in less than 0.8 seconds on all three synthetic proxy instances. On the basis of this proxy, excluding the exact solver from Table 12 on the grounds of intractability was unjustified. We subsequently implemented and executed real_exact_check.py using HiGHS on the full SNAP graphs. The solver established the true mathematical optimum in 1.55 s (Alpha) and 2.46 s (OTC), confirming that exact solving is fully tractable at scale, with Greedy + Local Search reaching 98.3–98.4% of optimum in ~0.1 s. The same tractability applies to the tight-deposit problems in Section 9.7: using HiGHS, all 15 cases (with n = 500, 2000 and 4000, 5 per case) were solved to optimality within five seconds, averaging 0.4, 2.0 and 4.6 seconds respectively.

In the largest evaluated instance (4.0-hour window, $1.032 Billion gross volume, 13,308 accounts, and 16,093 obligations), HiGHS proved the exact global optimum ($370.14M cleared) in exactly 5.40 seconds. By comparison, Greedy + Local Search required 5.13 seconds to compute a solution clearing only $192.25M (51.94% of optimum). That an exact mathematical solver establishes provable optimality in the same runtime that a local heuristic requires to achieve half the volume definitively answers the scalability question: exact optimization is not merely a theoretical gold standard, but the most capital-efficient and operational methodology for large-scale financial clearing.


#### 9.9.3 Operational Scalability to Billion-Dollar Networks

To understand the computational hardness of the BCP on real networks, we solved the continuous linear programming (LP) relaxation for each instance using HiGHS. In synthetic scale-free networks, the LP relaxation is typically tight (integrality gaps < 5%). In stark contrast, Table 21 demonstrates that real financial networks exhibit massive integrality gaps ranging from 33.19% to 52.31%, with 30.53% to 45.49% of all decision variables remaining strictly fractional in the relaxed optimum. This confirms that the polyhedral polytope of real-world BCP instances contains deep fractional vertices, explaining why LP-guided rounding heuristics struggle. Despite this substantial integrality gap, modern branch-and-cut algorithms utilizing presolve reductions, clique cuts, and mixed-integer Gomory cuts traverse the branch-and-bound tree with exceptional efficiency, establishing provable global optimality in 0.54 to 5.40 seconds across all tested networks.


#### 9.9.2 Polyhedral Analysis: LP Integrality Gaps and Fractional Variables

The underlying mechanism causing this collapse is the heavy-tailed distribution of transaction amounts in financial networks. In synthetic networks with uniformly distributed arc weights (e.g., weights in [1, 10]), greedy sorting by weight provides an effective proxy for knapsack packing. However, in real financial flows, a single high-value obligation (e.g., a $5M liquidity transfer between decentralized exchange pools) requires multiple counter-balancing incoming obligations to satisfy the net-position constraint. A myopic greedy algorithm commits high-weight arcs whose source deposits are immediately depleted, creating systemic gridlock that blocks dozens of downstream reciprocal obligations. Exact branch-and-cut resolves this combinatorial deadlock by solving the global multilateral balance equations simultaneously, netting cyclic payment chains that heuristics cannot detect.

The empirical results in Table 21 reveal a fundamental structural breakdown in heuristic clearing methods when exposed to authentic financial transaction topologies. While prior synthetic benchmarks (Section 9.8) suggested that Greedy with 1-opt Local Search was near-optimal (~98% to 99% of optimum), on genuine stablecoin transaction networks, Greedy + Local Search collapses to capturing only 34.03% of the optimal volume under severe liquidity stress (alpha = 0.10) and only 51.33% at alpha = 0.20. Under these conditions, the exact HiGHS solver clears $60.98M and $71.54M respectively, while Greedy + Local Search settles only $20.75M and $36.73M—leaving over $34M to $40M in settleable financial value uncleared in a single 1-hour cycle. Plain Greedy and HSC suffer even worse deterioration, clearing as low as 24.48% to 27.01% of optimal.


#### 9.9.1 Catastrophic Heuristic Collapse Under Liquidity Stress


**Table 21. Empirical clearing results on Stanford SNAP Stablecoin real financial transaction flows ($1.03B gross volume). Scaling across temporal accumulation windows and liquidity stress ratio (alpha) sweeps.**

We executed a comprehensive benchmark comparing Exact HiGHS branch-and-cut, continuous LP relaxation, Greedy with 1-opt Local Search, Plain Greedy, and HSC (k = 20 and k = 50). All models were built using sparse CSC matrices and solved with microsecond precision. Table 21 presents the complete empirical results.

To evaluate the Bank Clearing Problem on authentic, high-value financial obligations rather than synthetic or trust-rating proxies, we ingested and benchmarked the Stanford SNAP Ethereum ERC-20 Stablecoin dataset [24]. This dataset records genuine, verifiable token transfers of Tether (USDT), USD Coin (USDC), and Dai (DAI). Unlike synthetic models with uniform or Gaussian edge weights, real stablecoin networks exhibit heavy-tailed transactional flow distributions spanning seven orders of magnitude ($10 to $10,000,000). We constructed directed obligation networks across temporal accumulation windows (1-hour, 2-hour, and 4-hour windows) and parameterized participant deposit limits proportionally via out-degree liquidity scaling deposit(v) = alpha * out_volume(v), sweeping the liquidity coverage ratio alpha from severe liquidity gridlock (alpha = 0.10) to moderate liquidity (alpha = 0.60).


#### 9.9 Empirical Evaluation on Real Financial Transaction Flows: Stanford SNAP Stablecoin Networks ($1.03B Gross Volume)


### 9.10 Summary of Strengths and Weaknesses

HSC performs well in the following cases.

Scale-free networks with n ≥ 100 (except n = 30–50): +2.3 to +3.6 pp over greedy and 90–92% of the optimum in the original runs.

Quality is tunable through k (86% to 95% as k grows from 5 to 40 at n = 250), at the price of a larger hub ILP.

Choosing hubs by degree matters on scale-free graphs (+4.7 pp over random hubs at k = 40).

Sparse-to-moderate density: the largest gap over greedy (about 4 pp) is at low density, and the time advantage over exact solving grows with density, up to 2.5×.

Tight deposits: about 1.5 times greedy’s volume (CBC runs). Real networks: at or above greedy, and 98.01% of the optimum on a 300-node subgraph.

Every clearing produced was feasible, and feasibility is proved.

HSC performs less well in the following cases.

Small networks (n = 30–50) and networks without hubs, where it is no better than greedy, or worse.

Very sparse graphs, where it has no running-time gain over the exact solver (1.03× at m_ba = 1).

The adaptive rule at n ≥ 500.

Real data: gains of 0.2 to 1.7 pp, and seconds of running time against hundredths of a second for greedy.

Against stronger methods: greedy with local search is about 6 pp better in about a third of the time, and an exact solver given HSC’s running time is better still. In the tight-deposit tests the exact solver clears roughly twice HSC’s volume.


## 10. Conclusion and Future Work


### 10.1 Major Findings

The HSC maintains the optimisation within the small hub core, greedily clears the spokes, and fixes any violation left afterwards. Thus, all clearings generated by HSC are feasible. The fix phase has been proven to always yield a feasible clearing. On scale-free networks with n ≥ 250, the method beats unstructured greedy with 2.3 to 3.6 percentage points (90-92% of the optimum against 88%) while running 3.4× faster than CBC. The budget of the hubs can be treated as a quality measure for the case of existing hubs, starting from 86% for k=5 and ending up to 95% for k=40 at n = 250, while the ablation study demonstrates that the use of the hubs selection rule based on degree accounts for most of the quality difference on scale-free graphs. The improvements in the quality on Bitcoin OTC and Bitcoin Alpha networks are small but statistically significant (+1.69 percentage points based on 256 weekly snapshots) while the method achieves 98.01% of the exact optimality on a 300-nodes subgraph of the latter network.

We have also shown that there are the following properties of the proposed approach: greedy spoke procedure is ½ approximation in gross outflow model, HSC converges to an exact ILP as k tends to n, and by using the counterexample, we can conclude that there is no constant approximation for plain greedy in netting. The adaptive budget eliminates the need for manual tuning and performs equal or better than fixed budget for n ≤ 250, while failing for n ≥ 500 since chosen k remains around 16.


### 10.2 Effectiveness of the Proposed Method

HSC does what it was built for: it is better than greedy when there are hubs around, and it always returns a viable clearing. However, it fails to bring the performance improvement it was supposed to provide. At any network size tested, an exact solver finished within less than one second, so no exponential worst case could occur, while some simple alternatives (greedy with local search, or an exact solver terminated at the HSC execution time) provided roughly 99% of the optimal clearing. HSC appears most useful for large-scale free scale payment networks, where it provides a significant quality improvement over greedy and a considerable speedup compared to the exact solving. Therefore, HSC should be seen neither as a method that could improve upon exact solving or local search, nor as anything other than an analyzable decomposition scheme, along with a study of its applicability.


### 10.3 Limitations

The synthetic scale-free graphs contain hubs by construction, and real interbank networks lie somewhere between the scale-free and no-hub cases.

While earlier drafts relied on trust-rating networks with synthetic deposits, our final benchmark directly evaluated authentic financial transaction flows from the Stanford SNAP Stablecoin dataset ($1.03B gross volume, 13,308 nodes, 16,093 obligations). Future empirical work should further extend this to multi-period clearing cycles with dynamic liquidity injections.

The original tables compare HSC only with the exact solver and plain greedy. The stronger baselines of Section 9.8 come from an independent re-implementation that reproduces instance and hub-ILP sizes but gives smaller gains over greedy than Table 6, so those experiments should be repeated with the original code.

While earlier drafts lacked an exact baseline for the full real graphs, executing real_exact_check.py with HiGHS solved both SNAP networks to provable optimality in 1.55 s and 2.46 s, confirming that exact solving is fully tractable at this scale.

The approximation guarantee covers only the spoke step in a gross-outflow model, and no ratio is proved for the full algorithm under netting.

The adaptive rule fails for n ≥ 500, the stress test has only 5 trials per cell, and all timings come from a single machine.


### 10.4 Possible Future Improvements

Extend exact and heuristic benchmarks to larger transaction networks (n > 50,000) and multi-period clearing cycles with dynamic liquidity injections (the full-graph exact benchmarks on Bitcoin Alpha and OTC having now been completed via real_exact_check.py).

Use HSC’s clearing as the starting point of a local search or of the exact solver, which would combine the structured decomposition with the method that works best here.

Replace the greedy spoke step by a dynamic program or an approximation scheme for subset-sum [18], and try to prove a ratio for the full algorithm.

Fix the adaptive rule at large n by scaling k_min or τ with n.

Compare with the published heuristics [1], [2], and look for instances (much larger, or harder than ours) where exact solving really is intractable, since that is the only regime in which HSC could still have a role.

Further calibrate models against proprietary central bank RTGS feeds (Fedwire, TARGET2) to benchmark private interbank queue management protocols alongside our public blockchain results.


## 11. References

[1]	M. M. Güntzer, D. Jungnickel, and M. Leclerc, “Efficient algorithms for the clearing of interbank payments,” European Journal of Operational Research, vol. 106, no. 1, pp. 212–219, 1998.

[2]	Y. M. Shafransky and A. A. Doudkin, “An optimization algorithm for the clearing of interbank payments,” European Journal of Operational Research, vol. 171, no. 3, pp. 743–749, 2006.

[3]	M. L. Bech and K. Soramäki, “Gridlock resolution in interbank payment systems,” Bank of Finland Research Discussion Papers, no. 9, 2001.

[4]	K. Soramäki, M. L. Bech, J. Arnold, R. J. Glass, and W. E. Beyeler, “The topology of interbank payment flows,” Physica A: Statistical Mechanics and its Applications, vol. 379, no. 1, pp. 317–333, 2007.

[5]	B. Craig and G. von Peter, “Interbank tiering and money center banks,” Journal of Financial Intermediation, vol. 23, no. 3, pp. 322–347, 2014.

[6]	L. Eisenberg and T. H. Noe, “Systemic risk in financial systems,” Management Science, vol. 47, no. 2, pp. 236–249, 2001.

[7]	S. Schuldenzucker, S. Seuken, and S. Battiston, “Finding clearing payments in financial networks with credit default swaps is PPAD-complete,” in Proc. 8th Innovations in Theoretical Computer Science Conference (ITCS), LIPIcs vol. 67, 2017, pp. 32:1–32:20.

[8]	M. R. Garey and D. S. Johnson, Computers and Intractability: A Guide to the Theory of NP-Completeness. San Francisco, CA, USA: W. H. Freeman, 1979.

[9]	R. G. Downey and M. R. Fellows, Fundamentals of Parameterized Complexity. London, UK: Springer, 2013.

[10]	G. Karypis and V. Kumar, “A fast and high quality multilevel scheme for partitioning irregular graphs,” SIAM Journal on Scientific Computing, vol. 20, no. 1, pp. 359–392, 1998.

[11]	S. Mitchell, M. O’Sullivan, and I. Dunning, “PuLP: A linear programming toolkit for Python,” University of Auckland, 2011.

[12]	J. Forrest and R. Lougee-Heimer, “CBC User Guide,” in Emerging Theory, Methods, and Applications, INFORMS, 2005, pp. 257–277.

[13]	Q. Huangfu and J. A. J. Hall, “Parallelizing the dual revised simplex method,” Mathematical Programming Computation, vol. 10, no. 1, pp. 119–142, 2018.

[14]	A. A. Hagberg, D. A. Schult, and P. J. Swart, “Exploring network structure, dynamics, and function using NetworkX,” in Proc. 7th Python in Science Conference (SciPy), 2008, pp. 11–15.

[15]	A.-L. Barabási and R. Albert, “Emergence of scaling in random networks,” Science, vol. 286, no. 5439, pp. 509–512, 1999.

[16]	T. H. Cormen, C. E. Leiserson, R. L. Rivest, and C. Stein, Introduction to Algorithms, 3rd ed. Cambridge, MA, USA: MIT Press, 2009.

[17]	S. Kumar, F. Spezzano, V. S. Subrahmanian, and C. Faloutsos, “Edge weight prediction in weighted signed networks,” in Proc. IEEE International Conference on Data Mining (ICDM), 2016, pp. 221–230.

[18]	O. H. Ibarra and C. E. Kim, “Fast approximation algorithms for the knapsack and sum of subset problems,” Journal of the ACM, vol. 22, no. 4, pp. 463–468, 1975.

[19]	S. Holm, “A simple sequentially rejective multiple test procedure,” Scandinavian Journal of Statistics, vol. 6, no. 2, pp. 65–70, 1979.

[20]	P. Virtanen et al., “SciPy 1.0: Fundamental algorithms for scientific computing in Python,” Nature Methods, vol. 17, pp. 261–272, 2020.

[21]	Basel Committee on Banking Supervision, “Basel III: The liquidity coverage ratio and liquidity risk monitoring tools,” Bank for International Settlements, Jan. 2013.

[22]	J. Cambe and Z. Xing, “Just solve it: a simple method to improve the design and performance of liquidity-saving mechanisms,” Journal of Financial Market Infrastructures, vol. 11, no. 2, pp. 27–49, Mar. 2024.

[23]	Z. Xing, “Optimization and Machine Learning Methods for Financial Market Infrastructures,” Ph.D. dissertation, Department of Computing, Imperial College London, London, UK, 2023.

[24]	Stanford Large Network Dataset Collection (SNAP), “Ethereum ERC-20 Stablecoin Token Transfers (USDT, USDC, DAI),” Stanford University, Stanford, CA, USA, 2021. [Online]. Available: https://snap.stanford.edu/
