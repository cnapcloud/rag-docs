import Link from '@docusaurus/Link';
import Heading from '@theme/Heading';
import styles from './styles.module.css';
import {
  OverviewIcon,
  ConceptsIcon,
  GuidesIcon,
  OperationsIcon,
  ReferenceIcon,
  DemoIcon,
} from './icons';

const FeatureList = [
  {
    title: '개요',
    Icon: OverviewIcon,
    description: '3-Tier 아키텍처, 기능 카탈로그',
    to: '/overview/introduction',
  },
  {
    title: '개념',
    Icon: ConceptsIcon,
    description: '아키텍처, 검색·인제스트 흐름, 접근 제어',
    to: '/concepts/architecture',
  },
  {
    title: '가이드',
    Icon: GuidesIcon,
    description: 'RAG API / RAG Admin / RAG ENT 제품별 How-to',
    to: '/guides/rag-api/kb',
  },
  {
    title: '배포',
    Icon: OperationsIcon,
    description: '요구사항, k8s 설치, 백업/복구/업그레이드, 관측 구성',
    to: '/deploy/kubernetes',
  },
  {
    title: '레퍼런스',
    Icon: ReferenceIcon,
    description: 'API, 설정(settings.yaml), 환경변수(.env), Docker Compose 레퍼런스',
    to: '/reference/api-guide',
  },
  {
    title: '데모',
    Icon: DemoIcon,
    description: '데모 시나리오와 영상',
    to: '/demo/scenario',
  },
];

function Feature({title, Icon, description, to}) {
  return (
    <div className={styles.col}>
      <Link to={to} className={styles.feature}>
        <div className={styles.iconBadge}>
          <Icon />
        </div>
        <Heading as="h3" className={styles.featureTitle}>
          {title}
        </Heading>
        <p className={styles.featureDescription}>{description}</p>
      </Link>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <Heading as="h2" className={styles.sectionTitle}>
          문서 구성
        </Heading>
        <div className={styles.grid}>
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
