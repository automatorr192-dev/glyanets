import { Clock, MapPin, Phone } from '@phosphor-icons/react'
import { Cell, Group, NavBar } from '../components/ui'
import { STUDIO } from '../lib/data'
import { openLink } from '../lib/tg'

export function Studio() {
  return (
    <>
      <NavBar title="Студия" large sub="Два бокса, свет 6500 K, подъёмник" />

      <figure className="hero-photo inner rise" style={{ margin: '14px auto 0', maxWidth: 'calc(480px - 32px)', width: 'calc(100% - 32px)' }}>
        <img src="./studio.webp" alt="Мастер протирает микрофиброй глянцевый чёрный кузов" width="1200" height="750" loading="lazy" decoding="async" />
      </figure>

      <Group head="Как добраться" i={1}>
        <Cell icon={<MapPin size={19} weight="fill" />} title={STUDIO.address} sub={`м. ${STUDIO.metro}, 5 минут пешком`} chevron onClick={() => openLink(STUDIO.map)} />
        <Cell icon={<Clock size={19} weight="fill" />} title="Ежедневно" value="9:00-21:00" />
        <Cell icon={<Phone size={19} weight="fill" />} title="Позвонить" value={STUDIO.phone} href={`tel:${STUDIO.phone.replace(/[^\d+]/g, '')}`} />
      </Group>

      <Group head="Перед визитом" i={2}>
        <Cell title="Освободите салон и багажник" sub="Особенно перед химчисткой: мастер не тратит время на чужие вещи." />
        <Cell title="После керамики не мойте машину неделю" sub="Состав набирает твёрдость, ранняя мойка сокращает срок службы." />
        <Cell title="Принимайте работу в боксе" sub="Под нашим светом видно каждую риску, на улице вечером уже нет." />
      </Group>

      <Group head="Гарантия" i={3}>
        <Cell title="Керамика" value="2 года" />
        <Cell title="Бронеплёнка" value="5 лет" />
      </Group>

      <p className="fineprint inner">
        Демо-проект для портфолио: студия, цены и записи вымышлены, данные хранятся только на этом устройстве.
        <br />
        Дизайн и разработка: @automatorrr
      </p>
    </>
  )
}
