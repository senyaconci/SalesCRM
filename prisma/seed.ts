import { PrismaClient, Prisma } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  console.log("Seeding CapEx Signal CRM...");

  // Clean slate (dev only) — order matters for FK constraints.
  await prisma.projectAssignmentHistory.deleteMany();
  await prisma.activity.deleteMany();
  await prisma.note.deleteMany();
  await prisma.contact.deleteMany();
  await prisma.project.deleteMany();
  await prisma.workSession.deleteMany();
  await prisma.ownerOrganization.deleteMany();
  await prisma.vendorCustomer.deleteMany();
  await prisma.user.deleteMany();

  const passwordHash = await bcrypt.hash("password123", 10);

  const admin = await prisma.user.create({
    data: {
      name: "Avery Admin",
      email: "admin@capexsignal.com",
      passwordHash,
      role: "ADMIN",
    },
  });

  const manager = await prisma.user.create({
    data: {
      name: "Morgan Manager",
      email: "manager@capexsignal.com",
      passwordHash,
      role: "MANAGER",
    },
  });

  const sdr1 = await prisma.user.create({
    data: {
      name: "Sam Rivera",
      email: "sdr1@capexsignal.com",
      passwordHash,
      role: "SDR",
    },
  });

  const sdr2 = await prisma.user.create({
    data: {
      name: "Jordan Lee",
      email: "sdr2@capexsignal.com",
      passwordHash,
      role: "SDR",
    },
  });

  const cleaverBrooks = await prisma.vendorCustomer.create({
    data: {
      name: "Cleaver-Brooks",
      website: "https://cleaverbrooks.com",
      description: "Integrated boiler room and burner solutions.",
      targetGeography: "Southeast US",
      targetProjectTypes: "Boilers, Steam, Thermal Plants",
      notes: "Priority vendor. Fast follow-up expected.",
    },
  });

  const victoryEnergy = await prisma.vendorCustomer.create({
    data: {
      name: "Victory Energy",
      website: "https://victoryenergy.com",
      description: "Industrial steam generation systems.",
      targetGeography: "National",
      targetProjectTypes: "Steam, Thermal Plant",
    },
  });

  const rentech = await prisma.vendorCustomer.create({
    data: {
      name: "RENTECH",
      website: "https://rentechboilers.com",
      description: "Custom-engineered boilers and heat recovery.",
      targetGeography: "National",
      targetProjectTypes: "Boilers, Heat Recovery",
    },
  });

  const mckenna = await prisma.vendorCustomer.create({
    data: {
      name: "McKenna Boiler",
      website: "https://mckennaboiler.com",
      description: "Boiler service, rental, and installation.",
      targetGeography: "West Coast",
      targetProjectTypes: "Boilers, Steam",
    },
  });

  const uga = await prisma.ownerOrganization.create({
    data: {
      name: "University of Georgia",
      type: "UNIVERSITY",
      website: "https://uga.edu",
      state: "GA",
      city: "Athens",
      address: "Athens, GA 30602",
    },
  });

  const gradyHealth = await prisma.ownerOrganization.create({
    data: {
      name: "Grady Health System",
      type: "HOSPITAL",
      website: "https://gradyhealth.org",
      state: "GA",
      city: "Atlanta",
      address: "80 Jesse Hill Jr Dr SE, Atlanta, GA 30303",
    },
  });

  const miamiSchools = await prisma.ownerOrganization.create({
    data: {
      name: "Miami-Dade County Public Schools",
      type: "SCHOOL_DISTRICT",
      website: "https://dadeschools.net",
      state: "FL",
      city: "Miami",
    },
  });

  type ProjectSeed = {
    title: string;
    summary: string;
    evidenceText: string;
    category: Prisma.ProjectCreateInput["category"];
    stage: Prisma.ProjectCreateInput["stage"];
    status: Prisma.ProjectCreateInput["status"];
    priority: Prisma.ProjectCreateInput["priority"];
    budgetAmount: number;
    budgetText: string;
    locationCity: string;
    locationState: string;
    sourceUrl: string;
    ownerId: string;
    vendorId: string;
    assignedSdrId: string | null;
  };

  const projectSeeds: ProjectSeed[] = [
    {
      title: "Central Steam Plant Boiler Replacement",
      summary:
        "UGA is planning to replace two aging watertube boilers in its central steam plant to improve reliability and efficiency for campus heating.",
      evidenceText:
        "Board of Regents capital plan lists $8.5M for steam plant modernization at UGA, phase 1 boiler replacement scheduled to begin next fiscal year.",
      category: "BOILERS",
      stage: "PLANNING",
      status: "ASSIGNED",
      priority: "HIGH",
      budgetAmount: 8500000,
      budgetText: "$8.5M",
      locationCity: "Athens",
      locationState: "GA",
      sourceUrl: "https://usg.edu/capital/uga-steam-plant",
      ownerId: uga.id,
      vendorId: cleaverBrooks.id,
      assignedSdrId: sdr1.id,
    },
    {
      title: "Hospital Central Utility Plant Upgrade",
      summary:
        "Grady Health System is evaluating an upgrade of its central utility plant including new high-pressure steam boilers and controls.",
      evidenceText:
        "Facilities master plan references CUP resiliency upgrades; RFQ for engineering services posted for boiler and chiller plant assessment.",
      category: "THERMAL_PLANT",
      stage: "PRE_RFP",
      status: "NEW",
      priority: "URGENT",
      budgetAmount: 12000000,
      budgetText: "$12M (est.)",
      locationCity: "Atlanta",
      locationState: "GA",
      sourceUrl: "https://gradyhealth.org/procurement/cup-upgrade",
      ownerId: gradyHealth.id,
      vendorId: victoryEnergy.id,
      assignedSdrId: null,
    },
    {
      title: "District-Wide School Boiler Modernization",
      summary:
        "Miami-Dade schools bond program funds replacement of end-of-life boilers across a dozen campuses over multiple phases.",
      evidenceText:
        "2024 GO Bond project list allocates funds for HVAC and boiler replacements at 12 school sites; design underway for phase 1.",
      category: "BOILERS",
      stage: "DESIGN",
      status: "OUTREACH_STARTED",
      priority: "MEDIUM",
      budgetAmount: 6200000,
      budgetText: "$6.2M",
      locationCity: "Miami",
      locationState: "FL",
      sourceUrl: "https://dadeschools.net/bond/hvac-boilers",
      ownerId: miamiSchools.id,
      vendorId: mckenna.id,
      assignedSdrId: sdr2.id,
    },
    {
      title: "Steam Distribution Loop Rehabilitation",
      summary:
        "UGA plans rehabilitation of underground steam distribution piping and addition of a backup steam boiler for redundancy.",
      evidenceText:
        "Capital project brief notes deteriorating steam tunnels and need for N+1 boiler redundancy at the central plant.",
      category: "STEAM",
      stage: "PROPOSED",
      status: "CONTACTED",
      priority: "MEDIUM",
      budgetAmount: 4300000,
      budgetText: "$4.3M",
      locationCity: "Athens",
      locationState: "GA",
      sourceUrl: "https://usg.edu/capital/uga-steam-loop",
      ownerId: uga.id,
      vendorId: rentech.id,
      assignedSdrId: sdr1.id,
    },
    {
      title: "Emergency Boiler Rental & Replacement",
      summary:
        "Grady Health System needs temporary boiler rental capacity while planning a permanent replacement after a boiler failure.",
      evidenceText:
        "Emergency procurement notice for temporary steam boiler rental; permanent replacement to follow under separate capital request.",
      category: "BOILERS",
      stage: "IDENTIFIED",
      status: "VALIDATING",
      priority: "URGENT",
      budgetAmount: 1500000,
      budgetText: "$1.5M",
      locationCity: "Atlanta",
      locationState: "GA",
      sourceUrl: "https://gradyhealth.org/procurement/emergency-boiler",
      ownerId: gradyHealth.id,
      vendorId: cleaverBrooks.id,
      assignedSdrId: sdr2.id,
    },
  ];

  const buyerTitles = [
    { title: "Director of Facilities", relevance: "PRIMARY_DECISION_MAKER" as const },
    { title: "Energy Manager", relevance: "FACILITIES" as const },
    { title: "Procurement Officer", relevance: "PROCUREMENT" as const },
  ];

  const vendorTitles = [
    { title: "Regional Sales Manager", relevance: "PRIMARY_DECISION_MAKER" as const },
    { title: "Account Executive", relevance: "INFLUENCER" as const },
  ];

  for (const [index, seed] of projectSeeds.entries()) {
    const project = await prisma.project.create({
      data: {
        title: seed.title,
        summary: seed.summary,
        description: seed.summary,
        evidenceText: seed.evidenceText,
        category: seed.category,
        stage: seed.stage,
        status: seed.status,
        priority: seed.priority,
        budgetAmount: new Prisma.Decimal(seed.budgetAmount),
        budgetText: seed.budgetText,
        locationCity: seed.locationCity,
        locationState: seed.locationState,
        sourceUrl: seed.sourceUrl,
        ownerOrganizationId: seed.ownerId,
        vendorCustomerId: seed.vendorId,
        assignedSdrId: seed.assignedSdrId,
        projectOwnerId: manager.id,
        nextFollowUpAt:
          index % 2 === 0
            ? new Date(Date.now() + 1000 * 60 * 60 * 24 * (index + 1))
            : new Date(Date.now() - 1000 * 60 * 60 * 24),
      },
    });

    for (let i = 0; i < buyerTitles.length; i++) {
      const bt = buyerTitles[i];
      await prisma.contact.create({
        data: {
          projectId: project.id,
          organizationId: seed.ownerId,
          side: "BUYER",
          firstName: ["Pat", "Chris", "Taylor"][i],
          lastName: ["Johnson", "Nguyen", "Garcia"][i],
          fullName: `${["Pat", "Chris", "Taylor"][i]} ${["Johnson", "Nguyen", "Garcia"][i]}`,
          title: bt.title,
          email: `${["pat", "chris", "taylor"][i]}.buyer${index}@example.org`,
          phone: `+1404555${1000 + index * 10 + i}`,
          mobilePhone: `+1404555${2000 + index * 10 + i}`,
          relevance: bt.relevance,
          status: "NOT_CONTACTED",
          source: "CapEx Signal report",
        },
      });
    }

    for (let i = 0; i < vendorTitles.length; i++) {
      const vt = vendorTitles[i];
      await prisma.contact.create({
        data: {
          projectId: project.id,
          vendorCustomerId: seed.vendorId,
          side: "VENDOR",
          firstName: ["Alex", "Jamie"][i],
          lastName: ["Carter", "Wells"][i],
          fullName: `${["Alex", "Jamie"][i]} ${["Carter", "Wells"][i]}`,
          title: vt.title,
          email: `${["alex", "jamie"][i]}.vendor${index}@vendor.com`,
          phone: `+1470555${3000 + index * 10 + i}`,
          relevance: vt.relevance,
          status: "NOT_CONTACTED",
          source: "Vendor CRM",
        },
      });
    }
  }

  // A few example activities on the first project.
  const firstProject = await prisma.project.findFirst({
    where: { title: projectSeeds[0].title },
    include: { contacts: true },
  });

  if (firstProject) {
    const buyer = firstProject.contacts.find((c) => c.side === "BUYER");
    await prisma.activity.create({
      data: {
        projectId: firstProject.id,
        contactId: buyer?.id,
        userId: sdr1.id,
        type: "CALL",
        direction: "OUTBOUND",
        subject: "Intro call attempt",
        body: "Called facilities director, left a voicemail introducing CapEx Signal.",
        outcome: "LEFT_VOICEMAIL",
      },
    });
    await prisma.activity.create({
      data: {
        projectId: firstProject.id,
        contactId: buyer?.id,
        userId: sdr1.id,
        type: "EMAIL",
        direction: "OUTBOUND",
        subject: "CapEx Signal — Steam Plant Boiler Replacement",
        body: "Sent intro email with a short overview and asked for 15 minutes.",
        outcome: "SENT",
      },
    });
    await prisma.note.create({
      data: {
        projectId: firstProject.id,
        userId: sdr1.id,
        body: "Project looks well-funded per Board of Regents capital plan. Prioritize decision maker outreach.",
      },
    });
    await prisma.activity.create({
      data: {
        projectId: firstProject.id,
        userId: sdr1.id,
        type: "NOTE",
        direction: "INTERNAL",
        body: "Added research note about funding source.",
      },
    });
    await prisma.project.update({
      where: { id: firstProject.id },
      data: { lastActivityAt: new Date() },
    });
  }

  console.log("Seed complete.");
  console.log("Login accounts (password: password123):");
  console.log("  admin@capexsignal.com   (ADMIN)");
  console.log("  manager@capexsignal.com (MANAGER)");
  console.log("  sdr1@capexsignal.com    (SDR)");
  console.log("  sdr2@capexsignal.com    (SDR)");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
